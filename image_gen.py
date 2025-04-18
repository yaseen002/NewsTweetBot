import requests
import os

def generate_image(prompt, api_key, output_path):
    """
    Generate an image using Stability AI's API and save it to output_path.
    Returns the path to the saved image or raises an exception on failure.
    """
    try:
        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/ultra",
            headers={
                "authorization": f"Bearer {api_key}",
                "accept": "image/*"
            },
            files={"none": ''},
            data={
                "prompt": prompt,
                "output_format": "webp",
            },
        )
        if response.status_code == 200:
            with open(output_path, 'wb') as file:
                file.write(response.content)
            return output_path
        else:
            raise Exception(f"Image generation failed: {response.json()}")
    except Exception as e:
        raise Exception(f"Error generating image: {str(e)}")