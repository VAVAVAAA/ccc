from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from flask import Flask, request, jsonify
import socket
import time

app = Flask(__name__)

def find_available_port(start_port=5000, max_attempts=20):
    """自动寻找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
            return port
        except OSError:
            continue
    raise RuntimeError(f"未能在 {start_port}-{start_port+max_attempts} 范围内找到可用端口")

def extract_element_data(el):
    """根据元素类型提取数据"""
    tag = el.tag_name.lower()
    data = {"type": tag}
    
    if tag == "img" or el.get_attribute("src"):
        data.update({
            "src": el.get_attribute("src") or "",
            "alt": el.get_attribute("alt") or "",
            "width": el.size["width"],
            "height": el.size["height"]
        })
    else:
        text_content = el.text.strip()
        data.update({
            "text": text_content,
            "class": el.get_attribute("class") or "",
            "id": el.get_attribute("id") or ""
        })
        
        if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            data["heading_level"] = int(tag[1])
    
    return data

def crawl_with_xpaths(url, xpaths, simplified_output=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    result = {
        "status": "success",
        "url": url,
        "results": [],
        "error_count": 0,
        "timestamp": time.time()
    }
    
    try:
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(3)
        
        page_title = driver.title
        
        for xpath in xpaths:
            try:
                elements = WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located((By.XPATH, xpath))
                )
                
                items = []
                for idx, el in enumerate(elements, 1):
                    item = extract_element_data(el)
                    item["index"] = idx
                    items.append(item)
                
                if simplified_output:
                    for item in items:
                        item = {k: v for k, v in item.items() if v}
                
                result["results"].append({
                    "xpath": xpath,
                    "status": "success",
                    "count": len(items),
                    "items": items
                })
                
            except Exception as e:
                result["results"].append({
                    "xpath": xpath,
                    "status": "error",
                    "message": str(e)
                })
                result["error_count"] += 1
                
        result["page_title"] = page_title
        
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"全局错误: {str(e)}"
    finally:
        driver.quit()
        
    return result

@app.route('/crawl', methods=['POST'])
def crawl_api():
    if not request.is_json:
        return jsonify({"status": "error", "message": "请求必须是JSON格式"}), 400
        
    data = request.get_json()
    
    required_fields = ["url", "xpaths"]
    missing = [field for field in required_fields if field not in data]
    if missing:
        return jsonify({
            "status": "error",
            "message": f"缺少必要参数: {', '.join(missing)}"
        }), 400
        
    if not isinstance(data["xpaths"], list) or len(data["xpaths"]) == 0:
        return jsonify({
            "status": "error",
            "message": "xpaths必须是包含至少一个XPath的数组"
        }), 400
    
    use_simplified_format = data.get("simplified_format", True)
    result = crawl_with_xpaths(data["url"], data["xpaths"], simplified_output=True)
    
    if use_simplified_format:
        simplified_result = {"status": result["status"]}
        
        for xpath_result in result["results"]:
            if "h1" in xpath_result["xpath"] or any(item.get("type") == "h1" for item in xpath_result.get("items", [])):
                for item in xpath_result.get("items", []):
                    if item.get("type") == "h1":
                        simplified_result["title"] = item.get("text", "")
                        break
        
        img_list = []
        for xpath_result in result["results"]:
            if "img" in xpath_result["xpath"] or any(item.get("type") == "img" for item in xpath_result.get("items", [])):
                for item in xpath_result.get("items", []):
                    if item.get("type") == "img":
                        img_list.append({
                            "index": item.get("index", 0),
                            "src": item.get("src", ""),
                            "width": item.get("width", 0),
                            "height": item.get("height", 0)
                        })
        
        simplified_result["img"] = {
            "count": len(img_list),
            "items": img_list
        }
        
        return jsonify(simplified_result)
    
    return jsonify(result)

@app.route('/')
def home():
    return """
    <h1>智能网页元素抓取服务</h1>
    <p>POST /crawl 接口说明：</p>
    <pre>
    {
        "url": "目标网页URL",
        "xpaths": [
            "//img",                      
            "//h1",                       
            "//div[@class='content']"     
        ]
    }
    </pre>
    """

if __name__ == '__main__':
    port = find_available_port(5000)
    app.run(host="0.0.0.0", port=port, threaded=True)
