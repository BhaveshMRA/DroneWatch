import os
import asyncio
from google import genai
from google.genai import types

async def test_api():
    key = os.environ.get("GOOGLE_API_KEY", "")
    client = genai.Client(api_key=key)

    tools = [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="analyze_scene",
                description="Analyze scene.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
        ])
    ]
    config = types.GenerateContentConfig(tools=tools)

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents="What do you see?",
            config=config,
        )
        print("Model issued function call:", response.candidates[0].content.parts[0].function_call.name)
        
        # This is exactly what Orchestrator does:
        followup = [
            types.Content(role="user", parts=[types.Part(text="What do you see?")]),
            response.candidates[0].content,
            types.Content(role="user", parts=[types.Part(text="Tool results:\n[Vision]: CLEAR.\n\nRespond naturally.")]),
        ]
        
        print("Sending followup...")
        final = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=followup,
            config=types.GenerateContentConfig(),
        )
        print("Final:", final.text)
        
    except Exception as e:
        print(f"API ERROR CAUGHT: {type(e).__name__}: {str(e)}")

asyncio.run(test_api())
