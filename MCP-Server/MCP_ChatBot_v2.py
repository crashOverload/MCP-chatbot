from dotenv import load_dotenv
from google import genai
import json, os
from google.genai import types
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from typing import List
from contextlib import AsyncExitStack
import asyncio
import nest_asyncio

nest_asyncio.apply()
load_dotenv()
'''v2 connects to multiple mcp servers some of them remotely '''
class MCPChatbot:

    def __init__(self):
        # Initialize session and client objects
        self.sessions: List[ClientSession] = [] 
        self.exit_stack= AsyncExitStack() # A context manager that will manage the mcp client objects and their sessions and ensures that they are properly closed.
        self.client = genai.Client(api_key=os.getenv("GEMINI_KEY"))
        self.available_tools: List[dict] = [] #new empty list
        self.tool_to_session: dict[str, ClientSession] = {}  #manages 1:1 sessions for each tool servers

    async def connect_to_servers(self): # new
        """Connect to all configured MCP servers."""
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server configuration: {e}")
            raise

    async def connect_to_server(self, server_name:str, server_config: dict)-> None:
        """Connect to a single MCP server."""
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            ) # new
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            ) # new
            await session.initialize()
            self.sessions.append(session)
            
            # List available tools for this session
            response = await session.list_tools()
            tools = response.tools
            print(f"\nConnected to {server_name} with tools:", [t.name for t in tools])
            for tool in tools:
                print(tool)
                self.available_tools.append(tool)
                self.tool_to_session[tool.name] = session
        except Exception as e:
            print(f"Failed to connect to {server_name}: {e}")


    async def process_query(self, query):
        
        messages = [{'role': 'user', 'content': query}]
        
        response = self.client.models.generate_content(
            model='gemini-2.5-flash-preview-04-17',
            contents=json.dumps(messages),
            config={'tools':self.available_tools})
        process_query = True
        while process_query:
            assistant_content = []

            if response.text :
                assistant_content.append(response.text)
                print(response.text)
                #if len(response.text) == 1:
                process_query = False
            
            elif response.function_calls:
                for content in response.function_calls:
                    
                    assistant_content.append(json.dumps(content.to_json_dict()))
                    messages.append({'role': 'assistant', 'content': assistant_content})
                    
                    tool_id = content.id
                    tool_args = content.args
                    tool_name = content.name
                    
                    print(f"Calling tool {tool_name} with args {tool_args}")
                    
                    # Call a tool
                    #result = execute_tool(tool_name, tool_args): not anymore needed
                    # tool invocation through the client session
                     # Call a tool
                    session = self.tool_to_session[tool_name] # new
                    result = await session.call_tool(tool_name, arguments=tool_args)
                    call_tool_res = self.getResponseForCallTool(result)
                    messages.append({"role": "user", 
                                        "content": [
                                            {
                                                "type": "tool_result",
                                                "tool_name": tool_name,
                                                "content": call_tool_res
                                            }
                                        ]
                                    })
                    response = self.client.models.generate_content(
                                model='gemini-2.5-flash-preview-04-17',
                                contents= json.dumps(messages),
                                config={'tools':self.available_tools})

    def getResponseForCallTool(self, callToolResult:types.CallToolResult):
        results = callToolResult.content  # Assuming this is a CallToolResult
        return [result.text for result in results]


                    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
        
                if query.lower() == 'quit':
                    break
                    
                await self.process_query(query)
                print("\n")
                    
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self): # new
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()

    

async def main():
    chatbot = MCPChatbot()
    try:
        # the mcp clients and sessions are not initialized using "with"
        # like in the previous lesson
        # so the cleanup should be manually handled
        await chatbot.connect_to_servers() 
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup() 
  

if __name__ == "__main__":
    asyncio.run(main())