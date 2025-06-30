from typing import List, Union
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage
import os
from telegram import User
from langchain.memory import ConversationSummaryBufferMemory
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.mongo_memory import ChatMemory
from fastapi import HTTPException
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain_core.runnables import RunnableMap
import asyncio
from app.services.goals_service import UserGoalService
from app.services.agent_service import AgentService
from langchain.schema import SystemMessage
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.agents.openai_functions_agent.agent_token_buffer_memory import (
    AgentTokenBufferMemory,
)
from langchain.agents import AgentExecutor
from langchain.tools import Tool
import json
from app.services.user_service import UserService
import textwrap
from app.utils.util_func import get_current_time, get_mood_labels
from app.schemas.user_daily_mood_schema import UserDailyMood, UserDailyMoodPrediction
import datetime

# from transformers import pipeline

# emotion_classifier = pipeline(
#     "text-classification",
#     model="SamLowe/roberta-base-go_emotions",
#     top_k=None,
#     truncation=True,
# )


class LLMService:
    def __init__(self, db: AsyncIOMotorDatabase, uid: str):
        self.db = db
        self.llm = ChatOpenAI(
            temperature=0.7,
            model="gpt-3.5-turbo",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        self.uid = uid
        self.mood_collection = db["users_mood"]

    async def generate_greeting(
        self, first_name: str, username: str, is_new: bool, language: str
    ) -> str:
        prompt = PromptTemplate(
            input_variables=["first_name", "username", "is_new", "language"],
            template="""
                You are an AI assistant named Rune who helps people grow through daily reflection and goals.

                User Info:
                - Username: {username}
                - First Name: {first_name}
                - Is New User: {is_new}
                - Language Preference: {language}

                If the user is new, greet them warmly and explain the purpose of this assistant app in 2-3 sentences and point out that you need to gain information on the user's long term goals for you to break down into daily goals.
                If returning, welcome them back and remind them of their progress.

                Respond in a friendly, motivating tone.
            """,
        )

        chain = LLMChain(llm=self.llm, prompt=prompt)

        return await chain.arun(
            {
                "first_name": first_name,
                "username": username,
                "is_new": str(is_new).lower(),
                "language": language,
            }
        )

    async def reply_user_message(self, user: User, query: str) -> str:
        try:
            user_id = str(user.id)

            # Create memory instance
            chat_memory = ChatMemory(self.db, user_id)
            goal_service = UserGoalService(self.db, user_id)

            # Load existing messages from database into memory
            # Load existing goals from db
            memory_history = await chat_memory.load_messages_from_db()
            history = chat_memory.format_history_for_prompt(memory_history)

            # print("HISTORY ", str(history))
            system_prompt_rune_intro = f"""You are Rune, a warm, empathetic, and supportive AI companion whose purpose is to help users define, pursue, and accomplish their personal long-term goals through structured daily actions."""
            system_prompt_variables = f"""
                ## CONVERSATION VARIABLES
                User Info:
                Name: {user.first_name}
                Language: {user.language_code}
                Conversation history:
                {str(history)}
            """
            # TODO: Add default handler classification if not found
            system_prompt_task_classifier = f"""

                Your first task is to understand the user's query and classify into one of these list of classifications:
                - "greeting": If the user only greets you
                - "ask_goal_suggestions" : If the context of the conversation is about the user talking their goals or wanted you to give some suggestions on breaking down their long term goals into daily tasks
                - "save_discussed_goals" : If the context of the conversation is between you and user already talked about the goals and already have list of daily tasks and the user also agree about it
                - "daily_sharing" : If the context of conversation is about the user share you their day, or their progress, or anything they want to share. 
                
                Respond only using one key in the JSON format:
                "classification": "your_classification"

                Additional Instructions:
                ---
                ## Context Awareness and Memory
                - Always use the memory of conversation history (`history`) to understand the user's current state and context and avoid repetition.
                - If user already provided a goal in prior context, don't ask again. Refer to it directly.
                ---
                ## Personality
                Speak like a helpful and supportive friend.
                Be honest, warm, and non-judgmental.
                Encourage small steps and consistent effort.
                Gently redirect off-topic chats back to goals.
                ---
                ## Additional standard operation
                - Always ask for user confirmation upon proposing the structured goals
                
                {system_prompt_variables}
            """

            classifier_prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessagePromptTemplate.from_template(
                        system_prompt_task_classifier
                    ),
                    HumanMessagePromptTemplate.from_template("{input}"),
                ]
            )
            classifier_chain = classifier_prompt | self.llm
            classification_result = await classifier_chain.ainvoke({"input": query})

            parsed_classification = json.loads(classification_result.content)
            classification = parsed_classification.get("classification")

            print("CLASSIFICATION_RESULT " + classification)
            prompt = ""

            if classification == "ask_goal_suggestions":
                prompt = f"""{system_prompt_rune_intro}
                Understand and analyze the user intention and context based on user query input and conversation history.
                If user already state their goals, then your task is to analyze and break down the goals into daily achieveable tasks.
                Convert only to this following format example:
                Goal: "Learn Spanish fluently in 6 months"
                Daily Tasks:
                1. **Duolingo practice** - Complete 2 lessons (15-20 min)
                2. **Vocabulary flashcards** - Review 10 new words + 20 previous words
                3. **Spanish media** - Watch 1 Spanish YouTube video with subtitles
                ... 
                5. **Speaking practice** - Record yourself saying 5 sentences using today's vocabulary  
                The format of daily task should be **Name of the task** - (note or description) (times needed to complete eg: 10mins 1x a day, 1x a day, etc)
                Then, ask the user if they are agree for the daily tasks to be set. 
                {system_prompt_variables}
                """
            elif classification == "greeting":
                goals = await goal_service.load_goals()
                prompt = f"""{system_prompt_rune_intro}
                Greet back user the user. Then, check if goal provided is empty or None, then ask the user what is their current goal. 
                You can also ask for any kind of support they might need regarding their goals.
                Goals:
                {goals}
                {system_prompt_variables}
                """
            elif classification == "save_discussed_goals":
                convert_prompt = f"""{system_prompt_rune_intro}
                Analyze the conversation history and then find the daily tasks list that already agreed by the user. Then help the daily tasks into JSON format based on the 'UserGoal' class:
                    ** Begin classes **
                    class UserLongTermGoal(BaseModel):
                        summary: str
                        target_date: Optional[datetime]
                        status: str
                        created_at: datetime
                        updated_at: datetime

                    class UserDailyTask(BaseModel):
                        id: str
                        title: str
                        note: str
                        min_required_completion: int
                        completion_unit: str # times, minutes, hours
                        created_at: datetime
                        updated_at: datetime

                    class UserGoal(BaseModel):
                        id: str = Field(..., alias="_id")
                        long_term_goal: UserLongTermGoal
                        daily_tasks: List[UserDailyTask]
                        created_at: datetime
                        updated_at: datetime
                    ** end of classes **
                    Note: 
                    - You can fill "id" in "UserDailyTask" with the name of the task using snake_case. 
                    - Respond with JSON only as in HTTP REST API
                    - Make sure required property is filled!
                    {system_prompt_variables}
                """
                convert_chain = (
                    ChatPromptTemplate.from_messages(
                        [
                            SystemMessagePromptTemplate.from_template(convert_prompt),
                        ]
                    )
                    | self.llm
                )
                convert = await convert_chain.ainvoke({"input": query})
                print("CONVERT ", convert.content)
                save_res = await goal_service.save_goals(json.loads(convert.content))
                if save_res == "OK":
                    prompt = f"""{system_prompt_rune_intro}
                    Tell the user that goals have been set up. Say with positive validation and motivation to cheer up the user. And tell them that you wait the user update for today task
                    {system_prompt_variables}
                    """
                else:
                    prompt = f"""{system_prompt_rune_intro}
                    Tell the user that goals have not been set up. Apologize to the user, and please to try again later on.
                    {system_prompt_variables}
                    """
            elif classification == "daily_sharing":
                goals = await goal_service.load_goals()
                prompt = f"""{system_prompt_rune_intro}
                Here’s how you should respond:
                - Reflect back what the user is feeling, in your own words, to show that you truly understand.
                - Validate their emotions without judgment — make them feel heard, accepted, and safe.
                - If appropriate, gently normalize their experience (e.g., "It's completely understandable that you'd feel that way.")
                - End with an open, compassionate question or a gentle prompt to help them explore more if they wish.
                - If the user wants to skip the daily tasks. Make a way to gently remind the user that daily tasks are required to complete in order to achieve user's long-term goal

                Avoid giving advice (if not asked), making assumptions, or changing the subject. Your goal is to **hold space** for the user.
                Goals:
                {goals}
                {system_prompt_variables}
                """
            elif classification == "update_daily_task_progress":
                goals = await goal_service.load_goals()
                analyze_prompt = f"""{system_prompt_rune_intro}
                    Here is your tasks:
                    - Analyze, summarize, and **understand** the user query and intention.
                    - Find the corresponding goals matches the user query. Could be one of the daily tasks, could be more than one, or it could be all of the daily tasks
                    - Update the corresponding dictionary of the daily tasks according the user query and intention
                    - Result only using in JSON format with class as following:
                    {goals}
                    {system_prompt_variables}
                """
                analyze_chain = (
                    ChatPromptTemplate.from_messages(
                        [
                            SystemMessagePromptTemplate.from_template(analyze_prompt),
                            HumanMessagePromptTemplate.from_template("{input}"),
                        ]
                    )
                    | self.llm
                )

                analyze_chain_output = await analyze_chain.ainvoke({"input": query})

            reply_chain = (
                ChatPromptTemplate.from_messages(
                    [
                        SystemMessagePromptTemplate.from_template(prompt),
                        HumanMessagePromptTemplate.from_template("{input}"),
                    ]
                )
                | self.llm
            )
            reply_chain_output = await reply_chain.ainvoke({"input": query})
            reply = reply_chain_output.content

            await chat_memory.add_message_to_db(HumanMessage(content=query))
            await chat_memory.add_message_to_db(AIMessage(content=reply))

            return reply
        except Exception as e:
            raise str(e)

    async def ask_daily_sharing(self, name: str):
        try:
            # Create memory instance
            chat_memory = ChatMemory(self.db, self.uid)
            goal_service = UserGoalService(self.db, self.uid)

            memory_history = await chat_memory.load_messages_from_db()
            history = self.format_history_for_prompt(memory_history)

            goals = await goal_service.llm_load_goals()
            # print("HISTORY ", str(history))
            system_prompt = f"""You are Rune, a warm, empathetic, and supportive AI companion. Your purpose is to guide and uplift users as they pursue their personal long-term goals. You do this by helping them build self-awareness, reflect on their daily experiences, and translate intentions into structured daily actions.
                Your current task is to gently check in with the user. Begin the conversation by:
                - Asking how their day was in a natural or implicitly ask if they have something in mind, emotionally open-ended way. 
                - Asking the progress of their goal is second priority. The first priority comes to what are they feeling for today
                - Encouraging authentic reflection while being validating and supportive
                - Be gentle, warm, and attentive. Prioritize emotional connection and trust.
                - Your tone should always be supportive, calming, and empathetic.
                - Think other terms beside "How was your day?", use Thoughtful, Reflective, Friendly, and warm tone. use terms below as examples:
                    - What did today teach you?
                    - What moments stood out to you today?
                    - Where did your mind wander most today?
                    - What’s one thing you’re grateful for from today?
                    - How did today treat you?
                    - Catch me up—what did your day look like?
                - Your taks in this initial message is not to solve anything — just to open the door for honest reflection and emotional grounding.


                ## CONVERSATION VARIABLES
                User Info:
                Name: {name}
                Goals: {goals}
                Conversation history:
                {str(history)}
            """

            prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessagePromptTemplate.from_template(system_prompt),
                ]
            )
            chain = prompt | self.llm
            result = await chain.ainvoke({})

            await chat_memory.add_message_to_db(AIMessage(content=result.content))
            return result.content
        except Exception as e:
            print("ASK_DAILY_SHARE_ERR", e)
            raise ValueError(e)

    async def insert_mood_summary(
        self, name: str, dt: datetime = get_current_time("Asia/Jakarta")
    ):
        try:
            memories = ChatMemory(self.db, self.uid)
            goal_service = UserGoalService(self.db, self.uid)

            goals = await goal_service.llm_load_goals()
            histories = await memories.load_conversations_by_date(
                dt.strftime("%Y-%m-%d")
            )
            if not goals or not histories:
                return None

            llm_format_histories = memories.format_history_for_prompt(histories)

            system_prompt = textwrap.dedent(
                f"""
                You are an emotionally intelligent assistant trained in mood and sentiment analysis. 
                Analyze the user's conversation history and use the UserDailyMoodPrediction tool 
                to provide a structured emotional summary.

                ## USER CONTEXT
                Name: {name}
                Goals: {goals}

                ## CONVERSATION HISTORY
                {str(llm_format_histories)}
            """
            )

            llm_with_tools = self.llm.bind_tools([UserDailyMoodPrediction])

            response = llm_with_tools.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": "Please analyze my mood based on the conversation history above.",
                    },
                ]
            )

            if response.tool_calls:
                tool_call = response.tool_calls[0]
                mood_data = tool_call["args"]
                now = get_current_time("Asia/Jakarta")
                data = UserDailyMood(
                    telegram_id=self.uid,
                    date=dt.strftime("%Y-%m-%d"),
                    summary=mood_data["summary"],
                    mood_label=mood_data["mood_label"],
                    mood_polarity=mood_data["mood_polarity"],
                    motivation_level=mood_data["motivation_level"],
                    energy_level=mood_data["energy_level"],
                    task_completed=None,
                    task_skipped=None,
                    created_at=now,
                    updated_at=now,
                )
                await self.mood_collection.insert_one(data.model_dump())

                return data
            else:
                raise ValueError("No tool calls in response")
        except Exception as e:
            print(e)
            raise ValueError(str(e))

    async def get_mood_sentiment(
        self, name: str = "", dt: datetime = get_current_time("Asia/Jakarta")
    ):
        try:
            doc = await self.mood_collection.find_one(
                {"telegram_id": self.uid, "date": dt.strftime("%Y-%m-%d")}
            )
            if not doc:
                print("ANALYZE_NEW_MOOD")
                data = await self.insert_mood_summary(name)
                if not data:
                    return None
                return data.model_dump()
            print("EXISTING_MOOD")
            return UserDailyMood(**doc).model_dump()
        except Exception as e:
            print(e)
            raise ValueError(e)

    def mood_sentiment_to_text(self, data: dict) -> str:
        try:
            summary = data.get("summary", "No summary available")
            mood_label = data.get("mood_label", data.get("mood", "Unknown"))
            mood_polarity = data.get("mood_polarity", "neutral")
            motivation_level = data.get("motivation_level", "moderate")
            energy_level = data.get("energy_level", "moderate")
            date = data.get("date", "Today")

            polarity_emojis = {
                "positive": "😊",
                "negative": "😔",
                "neutral": "😐",
                "mixed": "🤔",
            }

            level_emojis = {"low": "🔻", "moderate": "➡️", "high": "🔺"}

            polarity_emoji = polarity_emojis.get(mood_polarity.lower(), "😐")
            motivation_emoji = level_emojis.get(motivation_level.lower(), "➡️")
            energy_emoji = level_emojis.get(energy_level.lower(), "➡️")

            message = textwrap.dedent(
                f"""
             *🗃 Daily Mood Summary* - {date}

            🎭 *Mood & Sentiment*
            *Sentiment:* {polarity_emoji}  {mood_polarity}
            *Mood:* {", ".join(mood_label)}

            📊 *Energy & Motivation:*
            Energy Level: {energy_emoji} `{energy_level}`
            Motivation: {motivation_emoji} `{motivation_level}`

            💭 *Summary:*
            {summary}

            _Any kind of telegram bot command related will not appended to Rune chat history_
            """
            )

            return message

        except Exception as e:
            raise ValueError(f"Error formatting mood data: {str(e)}")
