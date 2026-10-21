from dotenv import load_dotenv
load_dotenv()
import os
from tavily import TavilyClient

c = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
r = c.search("fact check claim: drinking cold water causes colds", max_results=3)
for x in r["results"]:
    print(x["title"], "|", x["url"])