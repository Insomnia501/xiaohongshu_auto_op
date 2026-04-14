import os
import time
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import requests
from volcenginesdkarkruntime import Ark

def _download_image(url: str, output_dir: str) -> str:
    """下载图片到指定的本地目录并返回保存的物理路径"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = int(time.time() * 1000)
    filename = f"img_{timestamp}.png"
    filepath = Path(output_dir) / filename
    
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    return str(filepath.absolute())

def generate_seedream_image(prompt: str, size: str = "1024x1024", model: str = "doubao-seedream-5-0-260128", output_dir: str = "images") -> dict:
    """调用火山引擎 Ark API 生成图片并保存本地"""
    # 从当前目录或向上查找 .env 并加载
    load_dotenv(find_dotenv())
    
    volc_api_key = os.getenv('VOLC_API_KEY') or os.getenv('ARK_API_KEY')
    if not volc_api_key:
        raise ValueError("Missing VOLC_API_KEY or ARK_API_KEY in environment variables.")

    client = Ark(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=volc_api_key, 
    )
    
    images_response = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        output_format="png",
        response_format="url",
        watermark=False
    )
    
    img_url = images_response.data[0].url
    local_path = _download_image(img_url, output_dir)
    
    return {
        "success": True,
        "image_url": img_url,
        "local_path": local_path,
        "prompt": prompt
    }
