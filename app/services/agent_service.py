from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationSummaryBufferMemory
from app.tools.goal_tool import save_goal_to_db, get_current_goal


class AgentService:
    def __init__(self, llm, chat_memory):
        self.memory = ConversationSummaryBufferMemory(
            llm=llm,
            chat_memory=chat_memory,
            return_messages=True,
            max_token_limit=1000,
        )
        self.agent = initialize_agent(
            tools=[save_goal_to_db, get_current_goal],
            llm=llm,
            agent=AgentType.OPENAI_FUNCTIONS,
            memory=self.memory,
            verbose=True,
        )

    async def run(self, input: str):
        return await self.agent.arun(input)
