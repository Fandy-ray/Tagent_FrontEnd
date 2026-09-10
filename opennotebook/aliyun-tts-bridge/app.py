from fastapi import FastAPI, Response
import requests
import os


app = FastAPI()


API_KEY = os.getenv("DASHSCOPE_API_KEY")


@app.get("/v1/models")
def models():

    return {
        "object":"list",
        "data":[
            {
                "id":"qwen3-tts-flash",
                "object":"model"
            }
        ]
    }



@app.post("/v1/audio/speech")
def speech(data:dict):

    text = data.get("input")


    payload = {
        "model":"qwen3-tts-flash",
        "input":{
            "text":text,
            "voice":"Cherry"
        }
    }


    response = requests.post(

        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",

        headers={
            "Authorization":f"Bearer {API_KEY}",
            "Content-Type":"application/json"
        },

        json=payload
    )


    result = response.json()


    audio_url = result["output"]["audio"]["url"]


    audio = requests.get(audio_url).content


    return Response(
        content=audio,
        media_type="audio/wav"
    )