from dotenv import load_dotenv
from google import genai
import json, os
from google.genai import types
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from typing import List
import asyncio
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

class MCPChatbot:

    def __init__(self):
        # Initialize session and client objects
        self.session: ClientSession = None
        self.client = genai.Client(api_key=os.getenv("GEMINI_KEY"))
        self.available_tools: List[dict] = []

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
                    result = await self.session.call_tool(tool_name, arguments=tool_args)
                    print(self.getResponseForCallTool(result))
                    messages.append({"role": "user", 
                                        "content": [
                                            {
                                                "type": "tool_result",
                                                "tool_name": tool_name,
                                                "content": self.getResponseForCallTool(result)
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


    async def connect_to_server_and_run(self):
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command="python",  # Executable
            args=["research_server.py"],  # Optional command line arguments
            env=None,  # Optional environment variables
        )
        # Launch the server as a subprocess & returns the read and write streams
        # read: the stream that the client will use to read msgs from the server
        # write: the stream that client will use to write msgs to the server
        async with stdio_client(server_params) as (read, write):
            # the client session is used to initiate the connection 
            # and send requests to server 
            async with ClientSession(read, write) as session:
                self.session = session
                # Initialize the connection (1:1 connection with the server)
                await session.initialize()
    
                # List available tools
                response = await session.list_tools()
                
                tools = response.tools
                print("\nConnected to server with tools:", [tool.name for tool in tools])
                #for anthropic
                '''self.available_tools = [{
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                } for tool in response.tools]'''
                
               
                #for google 
                self.available_tools = response.tools
                
                """[
                    types.Tool(
                        function_declarations=[
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": {
                                    k: v
                                    for k, v in tool.inputSchema.items()
                                    if k not in ["additionalProperties", "$schema"]
                                },
                            }
                        ]
                    )
                    for tool in response.tools
                ]"""
    
                await self.chat_loop()


async def main():
    chatbot = MCPChatbot()
    #await chatbot.process_query("find me 4 papers related to software engineering ")
    await chatbot.connect_to_server_and_run()
  

if __name__ == "__main__":
    asyncio.run(main())