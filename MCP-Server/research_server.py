from mcp.server.fastmcp import FastMCP
import papers

mcp = FastMCP("research")
#can also be done by adding an annotation @mcp.tool() to all the functions
mcp.add_tool(papers.search_papers)
mcp.add_tool(papers.extract_info)

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')

#RUN INSPECTOR WITH: npx @modelcontextprotocol/inspector python research_server.py
