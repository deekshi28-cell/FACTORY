import requests
import base64

def caption_image(image_path, prompt="Describe this image in one or two sentences, focusing on any technical details like diagrams, wiring, labels, or part numbers."):
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "qwen2.5vl:7b-q4_K_M",
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {
            "num_ctx": 8192   
        }
    })

    data = response.json()
    if "response" not in data:
        print(f"WARNING - unexpected response for {image_path}: {data}")
        return None

    return data["response"]

if __name__ == "__main__":
    test_image = r"D:\FactoryKA\extracted_images\7_p1_img0.png"
    caption = caption_image(test_image)
    print(f"Caption: {caption}")