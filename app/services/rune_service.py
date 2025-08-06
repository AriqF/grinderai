import asyncio
import json
import textwrap
from typing import List, Dict, Any, Optional
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import BaseTool
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
import os

from app.schemas.user_goals_schema import CreateUserGoal
from app.services.goals_service import UserGoalService
from app.services.mongo_memory import ChatMemory


# # Additional utility classes that you might need to implement
# class UserGoalService:
#     """Mock class - implement based on your existing service"""

#     def __init__(self, db, user_id):
#         self.db = db
#         self.user_id = user_id

#     async def load_goals(self):
#         pass

#     async def save_goals(self, goal_data):
#         pass

#     async def load_last_progresses(self, days):
#         pass

#     def format_progress_entries_to_text(self, progress):
#         pass


# class ChatMemory:
#     """Mock class - implement based on your existing memory system"""

#     def __init__(self, db, user_id):
#         self.db = db
#         self.user_id = user_id

#     async def load_messages_from_db(self):
#         pass

#     def format_history_for_prompt(self, history):
#         pass

#     async def add_message_to_db(self, message):
#         pass


class RuneChatbot:
    def __init__(self, db, llm):
        self.db = db
        self.llm = llm
        self.agent_executor = None
        self._setup_agent()

    def _setup_agent(self):
        """Initialize the agent with tools and memory"""
        tools = [
            self._create_goal_management_tool(),
            self._create_progress_tracking_tool(),
            self._create_sentiment_analysis_tool(),
            self._create_memory_tool(),
        ]

        # Create the system prompt for the agent
        system_prompt = self._get_system_prompt()

        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )

        # Create the agent
        agent = create_openai_functions_agent(llm=self.llm, tools=tools, prompt=prompt)

        # Create agent executor
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            max_iterations=3,
            early_stopping_method="generate",
        )

    def _get_system_prompt(self) -> str:
        return """You are Rune, a warm, empathetic, and supportive AI companion whose purpose is to help users define, pursue, and accomplish their personal long-term goals through structured daily actions.

## Your Core Personality:
- Speak like a helpful and supportive friend
- Be honest, warm, and non-judgmental
- Encourage small steps and consistent effort
- Gently redirect off-topic chats back to goals

## Your Capabilities:
You have access to several tools that help you:
1. Manage user goals and daily tasks
2. Track progress on daily tasks
3. Analyze user sentiment and mood
4. Access conversation history and context

## Key Guidelines:
- Always use conversation history to understand the user's current state
- If a user already provided a goal, refer to it directly
- Break down long-term goals into daily achievable tasks
- Always ask for user confirmation when proposing structured goals
- Provide emotional support and validation
- Celebrate progress and gently encourage when needed

Use your tools wisely to provide the most helpful and contextual responses."""

    def _create_goal_management_tool(self) -> BaseTool:
        """Tool for managing user goals and daily tasks"""

        @tool
        async def manage_goals(
            action: str = Field(
                description="Action to perform: 'load', 'save', 'suggest_breakdown'"
            ),
            user_id: str = Field(description="User ID"),
            goal_data: Optional[Dict] = Field(
                default=None, description="Goal data for saving"
            ),
            goal_text: Optional[str] = Field(
                default=None, description="Goal text for breakdown suggestions"
            ),
        ) -> str:
            """Manage user goals: load existing goals, save new goals, or suggest goal breakdowns"""

            goal_service = UserGoalService(self.db, user_id)

            if action == "load":
                goals = await goal_service.load_goals()
                return f"Current goals: {goals}" if goals else "No goals set yet."

            elif action == "save":
                print("GOAL_DATA ", goal_data)
                if not goal_data:
                    return "Error: No goal data provided for saving."
                # result = await goal_service.save_goals(goal_data)
                try:
                    # 1. Bind the CreateUserGoal tool to extract and validate structured goal data
                    llm_with_tools = self.llm.bind_tools([CreateUserGoal])

                    convert_prompt = textwrap.dedent(
                        f"""
                        Analyze and convert the following JSON-like goal input into valid 'UserGoal' objects with 'UserDailyTask' inside each. 
                        Ensure:
                        - Field 'id' in each daily task is in snake_case based on task name
                        - All required properties are filled
                        - Respond ONLY using tool format, no explanation or extra text.

                        Input goal data:
                        {goal_data}
                        """
                    )

                    response = await llm_with_tools.ainvoke(
                        [
                            {"role": "system", "content": convert_prompt},
                            {
                                "role": "user",
                                "content": "Please validate and structure this goal data into UserGoal format.",
                            },
                        ]
                    )

                    if response.tool_calls:
                        tool_call = response.tool_calls[0]
                        parsed_data = tool_call["args"]
                        print("PARSED_GOAL_DATA", parsed_data)

                        # Save using the goal service
                        result = await goal_service.save_goals(parsed_data)
                        return (
                            "Goals saved successfully!"
                            if result == "OK"
                            else "Failed to save goals."
                        )
                    else:
                        return "Failed to convert goal data. Please try again."
                except Exception as e:
                    print("[GOAL_SAVE_ERROR]", e)
                    return f"Error saving goals: {str(e)}"

            elif action == "suggest_breakdown":
                if not goal_text:
                    return "Error: No goal text provided for breakdown."

                # Generate daily task breakdown
                breakdown_prompt = f"""
                Break down this goal into daily achievable tasks: "{goal_text}"
                
                Format each task as:
                **Task Name** - Description (time/frequency needed)
                
                Requirements:
                - Tasks should be completable daily (not "3x per week")
                - Include specific time durations or counts
                - Make tasks concrete and measurable
                
                Example format:
                1. **Duolingo practice** - Complete 2 lessons (15-20 min daily)
                2. **Vocabulary review** - Study 10 new + 20 previous words (10 min daily)
                """

                breakdown_response = await self.llm.ainvoke(
                    [HumanMessage(content=breakdown_prompt)]
                )
                return breakdown_response.content

            return "Invalid action specified."

        return manage_goals

    def _create_progress_tracking_tool(self) -> BaseTool:
        """Tool for tracking daily task progress"""

        @tool
        async def track_progress(
            action: str = Field(
                description="Action: 'load_recent', 'update', 'analyze'"
            ),
            user_id: str = Field(description="User ID"),
            progress_data: Optional[Dict] = Field(
                default=None, description="Progress update data"
            ),
            days: int = Field(
                default=3, description="Number of days for recent progress"
            ),
        ) -> str:
            """Track and analyze user progress on daily tasks"""

            goal_service = UserGoalService(self.db, user_id)

            if action == "load_recent":
                progress = await goal_service.load_last_progresses(days)
                formatted_progress = goal_service.format_progress_entries_to_text(
                    progress
                )
                return f"Recent progress ({days} days):\n{formatted_progress}"

            elif action == "update":
                if not progress_data:
                    return "Error: No progress data provided."
                # Implementation would depend on your UserGoalService update method
                return "Progress updated successfully!"

            elif action == "analyze":
                progress = await goal_service.load_last_progresses(days)
                goals = await goal_service.load_goals()

                analysis_prompt = f"""
                Analyze this user's progress and provide insights:
                
                Goals: {goals}
                Recent Progress: {goal_service.format_progress_entries_to_text(progress)}
                
                Provide:
                1. What's going well
                2. Areas needing attention
                3. Encouraging suggestions
                """

                analysis = await self.llm.ainvoke(
                    [HumanMessage(content=analysis_prompt)]
                )
                return analysis.content

            return "Invalid action specified."

        return track_progress

    def _create_sentiment_analysis_tool(self) -> BaseTool:
        """Tool for analyzing user sentiment and mood"""

        @tool
        async def analyze_sentiment(
            user_id: str = Field(description="User ID"),
            days: int = Field(default=3, description="Number of days to analyze"),
            action: str = Field(
                default="analyze", description="Action: 'analyze' or 'load_history'"
            ),
        ) -> str:
            """Analyze user sentiment and mood over recent days"""

            if action == "load_history":
                mood_data = await self.get_mood_sentiment_last_days(days)
                return self.format_mood_entries_to_text(mood_data)

            elif action == "analyze":
                goal_service = UserGoalService(self.db, user_id)
                goals, progress, mood = await asyncio.gather(
                    goal_service.load_goals(),
                    goal_service.load_last_progresses(days),
                    self.get_mood_sentiment_last_days(days),
                )

                analysis_prompt = f"""
                Provide a comprehensive sentiment and progress analysis:
                
                Goals: {goals}
                Progress: {goal_service.format_progress_entries_to_text(progress)}
                Mood Data: {self.format_mood_entries_to_text(mood)}
                
                Analyze:
                1. Positive highlights
                2. Areas for improvement
                3. Emotional insights
                4. Encouraging suggestions
                
                Be warm and supportive in your analysis.
                """

                analysis = await self.llm.ainvoke(
                    [HumanMessage(content=analysis_prompt)]
                )
                return analysis.content

            return "Invalid action specified."

        return analyze_sentiment

    def _create_memory_tool(self) -> BaseTool:
        """Tool for accessing conversation history and context"""

        @tool
        async def access_memory(
            user_id: str = Field(description="User ID"),
            action: str = Field(
                default="load", description="Action: 'load' or 'summary'"
            ),
        ) -> str:
            """Access conversation history and provide context"""

            chat_memory = ChatMemory(self.db, user_id)
            memory_history = await chat_memory.load_messages_from_db()

            if action == "load":
                formatted_history = chat_memory.format_history_for_prompt(
                    memory_history
                )
                return f"Conversation history: {formatted_history}"

            elif action == "summary":
                # Create a summary of recent conversations
                if not memory_history:
                    return "No conversation history available."

                recent_messages = memory_history[-10:]  # Last 10 messages
                messages_text = "\n".join(
                    [f"{msg.type}: {msg.content}" for msg in recent_messages]
                )

                summary_prompt = f"""
                Summarize the key points from this conversation history:
                {messages_text}
                
                Focus on:
                - User's current goals and interests
                - Recent progress or challenges mentioned
                - User's emotional state or concerns
                - Any important context for future conversations
                """

                summary = await self.llm.ainvoke([HumanMessage(content=summary_prompt)])
                return summary.content

            return "Invalid action specified."

        return access_memory

    async def reply_user_message(self, user, query: str) -> str:
        """Main method to handle user messages using the agent"""
        try:
            user_id = str(user.id)

            # Create memory for this conversation
            print("fetchin memory")
            chat_memory = ChatMemory(self.db, user_id)
            memory_history = await chat_memory.load_messages_from_db()

            if memory_history is None:
                memory_history = []

            print("init agent input", memory_history)
            # Prepare the input for the agent
            agent_input = {
                "input": query,
                "chat_history": memory_history[-10:],  # Last 10 messages for context
                "user_id": user_id,
                "user_name": user.first_name,
                "user_language": user.language_code,
            }

            print("handling query")
            # Let the agent handle the query
            result = await self.agent_executor.ainvoke(agent_input)

            # Extract the response
            print("extracting response")
            response = result["output"]

            print("saving convo to memory")
            # Save the conversation to memory
            await chat_memory.add_message_to_db(HumanMessage(content=query))
            await chat_memory.add_message_to_db(AIMessage(content=response))

            return response

        except Exception as e:
            return f"I'm sorry, I encountered an error: {str(e)}. Please try again."

    # Helper methods (you'll need to implement these based on your existing code)
    async def get_mood_sentiment_last_days(self, days: int):
        """Load mood sentiment data for the last N days"""
        # Implement based on your existing mood tracking system
        pass

    def format_mood_entries_to_text(self, mood_entries):
        """Format mood entries to text"""
        # Implement based on your existing formatting logic
        pass


# Example usage and integration
class RuneChatbotService:
    """Service wrapper for the Rune chatbot"""

    def __init__(self, db):
        self.llm = ChatOpenAI(
            temperature=0.7,
            model="gpt-4o",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        self.chatbot = RuneChatbot(db, self.llm)

    async def handle_message(self, user, message: str) -> str:
        """Handle incoming user message"""
        return await self.chatbot.reply_user_message(user, message)
