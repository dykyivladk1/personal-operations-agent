# from typing import TypedDict, Literal

# from langgraph.graph import StateGraph, START, END
# from langchain_openai import ChatOpenAI


# class AgentState(TypedDict):
#     user_input: str
#     route: str
#     result: str


# llm = ChatOpenAI(
#     model = 'gpt-5.6',
#     temperature = 0
# )

# def router_node(state: AgentState):
#     response = llm.invoke(
#         f'''
#     Classify the folliwing request into exactly one category:
#     calendar
#     email
#     tasks
#     general
#     Return ONLY the category name.
#     Request: {state['user_input']}
#     '''
#     )

#     route = response.content.strip().lower()
#     return {
#         'route': route
#     }


# def calendar_agent(state: AgentState):
#     response = llm.invoke(
#         f'''
#         You are a calendar assistant.
#         Handle this request:
#         {state['user_input']}
#         '''
#     )
#     return {
#         'result': response.content
#     }


# def email_agent(state: AgentState):
#     response = llm.invoke(
#         f'''
#         You are an email assistant.
#         Handle this request:
#         {state['user_input']}
#         '''
#     )
#     return {
#         'result': response.content
#     }

# def task_agent(state: AgentState):
#     response = llm.invoke(
#         f'''
#         You are a task management assistant.
#         Handle this request:
#         {state['user_input']}
#         '''
#     )
#     return {
#         'result': response.content
#     }

# def general_agent(state: AgentState):
#     response = llm.invoke(state['user_input'])
#     return {
#         'result': response.content
#     }

# def choose_route(state: AgentState) -> Literal['calendar', 'email', 'tasks', 'general']:
#     route = state['route']
#     if route in {'calendar', 'email', 'tasks'}:
#         return route
#     return 'general'


# builder = StateGraph(AgentState)

# builder.add_node('router', router_node)
# builder.add_node('calendar', calendar_agent)
# builder.add_node('email', email_agent)
# builder.add_node('tasks', task_agent)
# builder.add_node('general', general_agent)

# builder.add_edge(START, 'router')

# builder.add_conditional_edges(
#     'router',
#     choose_route,
#     {
#         'calendar': 'calendar',
#         'email': 'email',
#         'tasks': 'tasks',
#         'general': 'general'
#     }
# )

# builder.add_edge('calendar', END)
# builder.add_edge('email', END)
# builder.add_edge('tasks', END)
# builder.add_edge('general', END)

# agent = builder.compile()


# if __name__ == '__main__':
#     result = agent.invoke({
#         'user_input': 'What meetings do I have tomorrow?',
#         'route': '',
#         'result': ''
#     })
#     print(result['result'])



from agent.tools import *