import tkinter as tk
from tkinter import messagebox, scrolledtext
import os
import sys
import platform
import shutil
import re

def run_compatibility_check():
    """시스템 점검 및 이전 설정 폴더 정리"""
    required = {
        'streamlit': 'streamlit', 'ollama': 'ollama', 'PyMuPDF': 'fitz',
        'python-docx': 'docx', 'beautifulsoup4': 'bs4', 'ebooklib': 'ebooklib',
        'pyperclip': 'pyperclip', 'pandas': 'pandas', 'lxml': 'lxml'
    }
    
    report = f"💻 OS: {platform.system()} {platform.release()}\n"
    report += f"🐍 Python: {sys.version.split()[0]}\n"
    report += "-"*30 + "\n"
    
    if os.path.exists(".streamlit"):
        try:
            shutil.rmtree(".streamlit")
            report += "🗑️ 테마 설정 초기화 완료\n"
        except: pass
    
    for package, import_name in required.items():
        try:
            __import__(import_name)
            report += f"✅ {package}: 설치됨\n"
        except ImportError:
            report += f"❌ {package}: 미설치\n"
    
    return report

def apply_changes():
    target_file = "main.py"
    if not os.path.exists(target_file):
        messagebox.showerror("에러", f"{target_file} 파일이 없습니다.")
        return

    new_church = entry_church.get().strip()
    new_api_key = entry_api.get().strip()

    if not new_church:
        messagebox.showwarning("주의", "교회 이름을 입력해주세요.")
        return

    try:
        new_lines = []
        
        # 파일 읽기 (인코딩 대응)
        encodings = ['utf-8-sig', 'utf-8', 'cp949']
        content = None
        for enc in encodings:
            try:
                with open(target_file, 'r', encoding=enc) as f:
                    content = f.readlines()
                break
            except UnicodeDecodeError: continue

        if content is None: raise Exception("파일을 읽을 수 없습니다.")

        for line in content:
            # 1. [2행] 주석 처리: v281.36. 뒤에 뭐가 있든 새 이름으로!
            if '# BibleAI v281.36.' in line:
                line = re.sub(r'# BibleAI v281\.36\..*', f'# BibleAI v281.36.{new_church}\n', line)
            
            # 2. [363행] 브라우저 탭: 따옴표 안을 통째로 교체
            elif 'page_title="' in line:
                line = re.sub(r'page_title=".*?"', f'page_title="{new_church}"', line)
            
            # 3. [737행] 사이드바: 🎂 v281.36. 뒤의 모든 문자를 교체
            elif 'st.title("🎂 v281.36.' in line:
                line = re.sub(r'st\.title\("🎂 v281\.36\..*?"\)', f'st.title("🎂 v281.36.{new_church}")', line)
            
            # 4. [844행] 메인 화면: ⚔️ 뒤의 모든 문자를 교체
            elif 'st.title("⚔️' in line:
                line = re.sub(r'st\.title\("⚔️.*?"\)', f'st.title("⚔️{new_church}")', line)

            # 5. [28행] API 키 교체
            if 'client = Groq(api_key=' in line:
                line = f'client = Groq(api_key="{new_api_key}")\n'
            
            new_lines.append(line)

        with open(target_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        messagebox.showinfo("성공", f"언어 통합 설정 완료!\n모든 위치가 '{new_church}'로 변경되었습니다.")
        root.destroy()
            
    except Exception as e:
        messagebox.showerror("실패", f"오류 발생: {str(e)}")

# --- GUI 구성 ---
root = tk.Tk()
root.title("BibleAI 언어 통합 설정 도구")
root.geometry("450x550")
root.configure(bg="#F5F5DC")

bg_color = "#F5F5DC"
tk.Label(root, text="[ 1단계: 시스템 점검 ]", font=("맑은 고딕", 11, "bold"), bg=bg_color).pack(pady=10)
log_area = scrolledtext.ScrolledText(root, width=50, height=10, font=("Consolas", 9))
log_area.pack(pady=5)
log_area.insert(tk.END, run_compatibility_check())
log_area.configure(state='disabled')

tk.Label(root, text="[ 2단계: 교회명 통합 설정 ]", font=("맑은 고딕", 11, "bold"), bg=bg_color).pack(pady=10)
tk.Label(root, text="새로운 교회명 (한글/영문 모두 가능):", bg=bg_color).pack()
entry_church = tk.Entry(root, width=30)
entry_church.pack(pady=5)

tk.Label(root, text="Groq API Key:", bg=bg_color).pack()
entry_api = tk.Entry(root, width=40)
entry_api.pack(pady=5)

btn = tk.Button(root, text="모든 위치 언어 통합 적용", command=apply_changes, 
                bg="#8D6E63", fg="white", font=("맑은 고딕", 10, "bold"), padx=20, pady=10)
btn.pack(pady=20)

root.mainloop()