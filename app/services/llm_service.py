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


class LLMService:
    def __init__(self, db: AsyncIOMotorDatabase, uid: str):
        self.db = db
        self.llm = ChatOpenAI(
            temperature=0.7,
            model="gpt-3.5-turbo",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )

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
            history = self.format_history_for_prompt(memory_history)

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

    def format_history_for_prompt(
        self,
        messages: List[Union[AIMessage, HumanMessage]],
    ) -> str:
        """Convert message history to a safe string format for prompts"""
        if not messages:
            return "No previous conversation history."

        formatted_history = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                # Escape curly braces and format safely
                content = msg.content.replace("{", "{{").replace("}", "}}")
                formatted_history.append(f"User: {content}")
            elif isinstance(msg, AIMessage):
                content = msg.content.replace("{", "{{").replace("}", "}}")
                formatted_history.append(f"Rune: {content}")

        return "\n".join(formatted_history)
