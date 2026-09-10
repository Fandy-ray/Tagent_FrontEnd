from typing import Annotated

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from app.repository.provider_repository import load_model_registry
load_dotenv()


def create_default_llm():
    provider = load_model_registry().get_enabled_provider()
    model_config = provider.as_openai_config
    return ChatOpenAI(
        model=model_config.model,
        base_url=model_config.base_url,
        api_key=model_config.api_key,
        temperature=model_config.temperature,
    )

class State(TypedDict):  # 继承TypedDict就可以用dict表示了State了
    # 还记得上吗怎么介绍State的么？对，它是传递信息的载体。
    #
    # 这里我们定一个list类型State
    # 并为它添加元数据add_messages function,框架将通过这个function来reduce数据，
    # add_messages作用是将多个message list合并为一个
    messages: Annotated[list, add_messages]


# 定义graph
graph_builder = StateGraph(State)


# 使用一个function在node运行时调用
def chatbot(state: State):
    # 返回一个State dict
    llm = create_default_llm()
    return {"messages": [llm.invoke(state["messages"])]}


# 添加node
# 第一个参数为node的名称，第二个参数为node被使用时调用的方法
graph_builder.add_node("chatbot", chatbot)

# 添加一个入口
graph_builder.add_edge(START, "chatbot")
# 添加一个出口，任何node都可以指向出口
graph_builder.add_edge("chatbot", END)
# 最后如果想让我们的graph运行，我们需要将graph进行编译。它将返回一个compiledGraph
graph = graph_builder.compile()

if __name__ == "__main__":
    for event in graph.stream({"messages": [("user", "hello")]}):
        print(event)
