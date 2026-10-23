import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

import pyautogui
import pyperclip
import pygetwindow

OUT = Path.home() / "ShopeeCollector"
RAW = OUT / "captures.jsonl"
LINKS = OUT / "product_links.jsonl"


def activate_shopee():
    windows = [w for w in pygetwindow.getAllWindows() if "shopee" in (w.title or "").lower()]
    if not windows:
        print("未找到标题包含 Shopee 的窗口。请先在紫鸟 LXN92:MAIN 打开 Shopee 页面。")
        return False
    target = windows[0]
    try:
        if target.isMinimized:
            target.restore()
        target.activate()
    except Exception as exc:
        print(f"无法激活 Shopee 窗口：{exc}")
        return False
    time.sleep(2)
    active = pygetwindow.getActiveWindowTitle() or ""
    if "shopee" not in active.lower():
        print(f"Shopee 窗口未取得焦点，当前活动窗口：{active}")
        return False
    print(f"已激活窗口：{active}")
    return True


def copy_url():
    active = pygetwindow.getActiveWindowTitle() or ""
    if "shopee" not in active.lower():
        return ""
    pyperclip.copy("")
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.8)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(1)
    url = pyperclip.paste().strip()
    pyautogui.press("esc")
    return url


def copy_page_text():
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "c")
    time.sleep(1)
    return pyperclip.paste()


def copy_product_links():
    script = "script:(()=>{const a=[...document.querySelectorAll('a[href]')].map(x=>x.href).filter(x=>/-i\\.\\d+\\.\\d+/.test(x)||/\\/product\\/\\d+\\/\\d+/.test(x));prompt('SHOPEE_LINKS',[...new Set(a)].join('\\n'))})()"
    pyautogui.hotkey("ctrl", "l")
    pyautogui.write("java", interval=0.08)
    pyperclip.copy(script)
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("enter")
    time.sleep(2)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.5)
    value = pyperclip.paste()
    pyautogui.press("esc")
    return [line.strip() for line in value.splitlines() if line.strip().startswith("http")]


def parse_zhixia(text):
    blocks = re.split(r"(?=商品ID\s*[:：])", text)
    rows = []
    for block in blocks:
        product_id = re.search(r"商品ID\s*[:：]\s*(\d+)", block)
        if not product_id:
            continue
        def value(pattern):
            match = re.search(pattern, block)
            return match.group(1).strip() if match else ""
        rows.append({
            "product_id": product_id.group(1),
            "listed_at": value(r"上架时间\s*[:：]\s*([^\r\n]+)"),
            "likes": value(r"点赞数\s*[:：]\s*([\d,.]+)"),
            "reviews": value(r"评论数\s*[:：]\s*([\d,.]+)"),
            "rating": value(r"商品评分\s*[:：]\s*([\d.]+)"),
            "sales_7d": value(r"近1天/7天销量[^:：]*[:：]\s*([^\r\n]+)"),
            "sales_30d": value(r"近30天销量[^:：]*[:：]\s*([\d,.]+)"),
            "growth_30d": value(r"近30天销量增长率\s*[:：]\s*([\d,.%-]+)"),
        })
    return rows


def capture():
    if not activate_shopee():
        return
    url = copy_url()
    if not url.startswith("http") or "shopee" not in url.lower():
        active = pygetwindow.getActiveWindowTitle() or ""
        print(f"采集已取消：未复制到 Shopee 地址。当前窗口：{active}；读取到：{url[:80]}")
        return
    text = copy_page_text()
    rows = parse_zhixia(text)
    links = copy_product_links()
    link_map = {}
    for link in links:
        match = re.search(r"(?:-i\.|/product/)(\d+)[./](\d+)", link)
        if match:
            link_map[match.group(2)] = link
    for row in rows:
        row["product_url"] = link_map.get(row["product_id"], "")
    OUT.mkdir(parents=True, exist_ok=True)
    record = {"captured_at": datetime.now().isoformat(), "page_url": url, "items": rows}
    with RAW.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"已保存 {len(rows)} 个商品，其中 {sum(bool(r['product_url']) for r in rows)} 个已取得链接：{RAW}")


def capture_product_link():
    if not activate_shopee():
        return
    url = copy_url()
    if not url.startswith("http") or "shopee" not in url.lower():
        print(f"采集已取消：当前焦点不在 Shopee 商品页（读取到：{url[:80]}）")
        return
    match = re.search(r"(?:-i\.|/product/)(\d+)[./](\d+)", url)
    item_id = match.group(2) if match else ""
    OUT.mkdir(parents=True, exist_ok=True)
    with LINKS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"captured_at": datetime.now().isoformat(), "product_id": item_id, "url": url}, ensure_ascii=False) + "\n")
    print(f"已保存商品链接：{url}")


def export_csv():
    unique = {}
    if not RAW.exists():
        print("还没有采集数据。")
        return
    link_map = {}
    if LINKS.exists():
        for line in LINKS.read_text(encoding="utf-8").splitlines():
            link = json.loads(line)
            if link.get("product_id"):
                link_map[link["product_id"]] = link["url"]
    for line in RAW.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        for item in record["items"]:
            item["source_page"] = record["page_url"]
            item["product_url"] = item.get("product_url") or link_map.get(item["product_id"], "")
            def number(value):
                match = re.search(r"-?[\d,.]+", str(value or ""))
                return float(match.group().replace(",", "")) if match else 0.0
            reasons = []
            if number(item.get("sales_30d")) >= 20:
                reasons.append("近30天销量>=20")
            if number(item.get("growth_30d")) >= 30:
                reasons.append("增长率>=30%")
            if number(item.get("likes")) >= 200:
                reasons.append("点赞>=200")
            item["selected"] = "是" if reasons else "否"
            item["selection_reason"] = "；".join(reasons)
            unique[item["product_id"]] = item
    target = OUT / "zhixia_candidates.csv"
    fields = ["product_id", "listed_at", "likes", "reviews", "rating", "sales_7d", "sales_30d", "growth_30d", "selected", "selection_reason", "product_url", "source_page"]
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(unique.values())
    print(f"已导出 {len(unique)} 个去重商品：{target}")
    selected = OUT / "selected_candidates.csv"
    with selected.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(item for item in unique.values() if item["selected"] == "是" and item["product_url"])
    print(f"自动入选且有链接的商品已导出：{selected}")


def main():
    pyautogui.PAUSE = 0.25
    print("Shopee/知虾本地采集助手")
    while True:
        choice = input("\n1 采集当前知虾列表页\n2 导出去重CSV\n3 采集当前Shopee商品链接\n0 退出\n请选择：").strip()
        if choice == "1":
            capture()
        elif choice == "2":
            export_csv()
        elif choice == "3":
            capture_product_link()
        elif choice == "0":
            break


if __name__ == "__main__":
    main()
