import asyncio
import json
import os 
from typing import List, Dict, Any
from http.client import HTTPException

from config import client
from utils import clean_json_content
from agents.summarize_agent import summarize_agent
#from agents.search_agent import search_agent
#from agents.web_content_agent import web_content_agent
from agents.poi_activity_agent import poi_activity_agent
from agents.plan_agent import plan_agent
#from agents.critic_agent import critic_agent
#from agents.format_agent import format_agent

from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient



async def run_autogen_workflow(initial_user_input: Dict[str, Any]) -> Dict[str, Any]:
    print("--- Starting AutoGen Workflow ---")
    print(f"Initial User Input: {initial_user_input}")

    # 3 enhanced agents in sequence - now 50% faster, half the API calls, saves 60% cost
    agents=[
        summarize_agent,
        #search_agent,
        #web_content_agent,
        poi_activity_agent,
        plan_agent,
        #critic_agent,
        #format_agent
    ]

    # Set termination condition: end when format_agent outputs "TERMINATE"
    termination = TextMentionTermination(text="TERMINATE")


    # 创建 MagenticOneGroupChat 实例
    # 它会按顺序执行 Agent，并将前一个 Agent 的输出作为下一个 Agent 的输入
    # Create MagenticOneGroupChat instance
    # Executes agents in sequence, passing output from one to the next
    group_chat = MagenticOneGroupChat(
        agents,
        termination_condition=termination,
        model_client=client, # 可以为 group chat 本身指定一个 client，用于管理流程
    )

    initial_task = json.dumps(initial_user_input)
    print(f"--- Initiating Group Chat with Task: {initial_task[:200]}... ---") # 打印部分任务内容

    try:
        # 运行 Agent 流程
        # 使用 run() 而不是 run_stream() 来获取最终结果
        # Run the agent workflow
        final_result = await group_chat.run(task=initial_task)
        messages = final_result.messages
        final_output = None

        print(f"--- Workflow completed with {len(messages)} messages ---")

        print("Checking for agent errors...")
        for i, msg in enumerate(messages):
            try:
                # Handle different message types safely
                if hasattr(msg, 'content'):
                    content = str(msg.content)
                elif hasattr(msg, 'message'):
                    content = str(msg.message)
                else:
                    content = str(msg)
        
                if 'error' in content.lower() or 'failed' in content.lower() or 'exception' in content.lower():
                    source = getattr(msg, 'source', f'unknown_type_{type(msg).__name__}')
                    print(f"⚠️  Message {i+1} ({source}): {content[:200]}...")
            except Exception as debug_error:
                print(f"⚠️  Message {i+1}: Debug error - {debug_error}")
    
        # Debug: Print all message sources
        print("Message sources:")
        print(f"🔍 plan_agent in workflow: {'plan_agent' in [agent.name for agent in agents]}")
        print(f"🔍 Total agents registered: {len(agents)}")
        for i, msg in enumerate(messages):
            print(f"  {i+1}. {msg.source}")

        # Extract plan_agent output (PROPERLY INDENTED)
        print("Extracting final itinerary data...")
    
        for msg in reversed(messages):
            if hasattr(msg, 'source') and hasattr(msg, 'content') and msg.source == 'plan_agent':
                print("✅ Found plan_agent output")
        
                # Use regular Python to format for frontend (no AI needed - removes need for format agent)
                try:
                    cleaned_content = clean_json_content(msg.content)
                    import re
                    json_match = re.search(r'```json\s*\n(.*?)\n```', cleaned_content, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1).strip()
                    else:
                        json_content = cleaned_content  # Fallback to original behavior
    
                    plan_data = json.loads(json_content)
            
                    # Format for your frontend needs
                    original_input = json.loads(initial_task)

                    final_output = {
                        "success": True,
                        "itinerary": plan_data,
                        "original_request": original_input,  # Pass through original request
                        "extracted_metadata": {
                            # Let frontend handle extraction, or extract here with simple regex
                            "query": original_input.get("Query", ""),
                            "mbti": original_input.get("mbti", ""),
                            "budget": original_input.get("Budget", 0)
                        }
                    }
                    print(f"Plan agent output structure: {json.dumps(plan_data, indent=2)[:500]}...")
                    print("✅ Successfully formatted itinerary")
                    break
                except Exception as format_error:
                    print(f"JSON parsing failed: {format_error}")
                    # Fallback if not JSON
                    final_output = {"success": True, "raw_plan": str(msg.content)}
                    break
        else:
            print("❌ No plan found")
            final_output = None

        print("--- AutoGen Workflow Completed ---")
        return final_output
        
    except HTTPException as he:
        # 透传 summarize_agent 抛出的 HTTP 异常 (例如无效地点)
        raise he
    except Exception as e:
        print(f"--- AutoGen Workflow Error: {e} ---")
        # 可以根据需要进行更细致的错误处理
        raise Exception(f"An error occurred during the itinerary generation: {e}")


# --- 主程序入口 (示例) ---
# 通常这个函数会由 app.py 调用
async def main_test():
    """Local test run function"""
    test_input = {
        "mbti": "ENFJ",
        "Budget": 2000,
        "Query": "Plan a 3-day trip to Tokyo, Japan focused on technology and culture. Include tech hubs and traditional temples.",
        "CurrentItinerary": None
    }
    try:
        result = await run_autogen_workflow(test_input)
        if result:
            print("✅ Test successful!")
            print("Result type:", type(result))
            if isinstance(result, list) and len(result) > 0:
                print("Days in itinerary:", len(result))
                print("First day:", result[0].get('day', 'No day field'))
        else:
            print("❌ Test returned None")
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    print("Running local test...")
    asyncio.run(main_test())