import streamlit as st
import google.generativeai as genai
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pandas as pd

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(page_title="시디즈 UX 번역기", page_icon="💺", layout="wide")

# ==========================================
# 2. Google Sheets 설정
# ==========================================
def get_gsheet_client():
    """Google Sheets 클라이언트 초기화"""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Google Sheets 연동 오류: {e}")
        return None

def save_feedback_to_sheet(original_text, converted_text, feedback):
    """피드백을 Google Sheets에 저장"""
    try:
        client = get_gsheet_client()
        if client is None:
            return False
        
        sheet_url = st.secrets.get("feedback_sheet_url", "")
        if not sheet_url:
            st.warning("⚠️ feedback_sheet_url이 Secrets에 설정되지 않았습니다.")
            return False
        
        # 시트 열기
        sheet = client.open_by_url(sheet_url).sheet1
        
        # 데이터 추가
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 시간
            original_text,                                  # 원본 문구
            converted_text,                                 # 변환된 문구
            "👍" if feedback == 1 else "👎",               # 피드백
            feedback                                        # 피드백값 (1 or 0)
        ]
        
        sheet.append_row(row)
        return True
        
    except Exception as e:
        st.error(f"저장 오류: {e}")
        return False

# ==========================================
# 3. Gemini API 설정
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=GOOGLE_API_KEY)
    
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    
    st.success(f"✅ 모델 로드 완료: {target}")
    
except KeyError as e:
    st.error(f"❌ Secrets 설정 오류: {e}")
    st.info("💡 Streamlit Cloud 설정에서 다음을 추가하세요:")
    st.code("""
[gemini]
api_key = "your_gemini_api_key"

feedback_sheet_url = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
    """)
    st.stop()

# ==========================================
# 4. 브랜드 가이드라인
# ==========================================
SYSTEM_INSTRUCTION = '''너는 시디즈의 UX 라이터야. 일반적인 문구를 시디즈만의 [전문적/세심한/혁신적] 톤으로 바꿔줘.
아래는 시디즈 홈페이지에서 가져온 브랜드 문구들이야. 이 말투와 단어 선택을 학습해서 내 문장을 변환해줘.

[참고 문구]
- 시디즈의 디자인은 사용자로부터 시작됩니다. 누가 앉을지, 어떤 상황에서 쓰일지 고민하여 최상의 의자 위 경험이라는 시팅 솔루션을 구현해냅니다.
- 인체에 대한 다양한 연구와 공학적 설계를 통해 누구든지 편안하게 사용할 수 있는 제품을 완성합니다.
- 언제나 새로운 시도를 주저 않고, 전문성을 더해 의자 위의 가장 진보된 경험을 만듭니다.
- 제품 구매가 기능적 가치를 넘어 지속가능성을 이루는 방식이 되도록 책임을 다합니다.
- 어떤 상황과 자세에서도 유연하게 반응하며 모든 니즈에 대응하는 퍼포먼스 공학 의자와 함께하세요.
'''

# ==========================================
# 5. 모델 초기화
# ==========================================
@st.cache_resource
def get_gemini_model():
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    return genai.GenerativeModel(target)

# ==========================================
# 6. UI 구성
# ==========================================
st.title("💺 시디즈 UX 라이팅 번역기")
st.markdown("---")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback_data" not in st.session_state:
    st.session_state.feedback_data = {}

if "feedback_saved" not in st.session_state:
    st.session_state.feedback_saved = set()

# ==========================================
# 7. 사이드바
# ==========================================
with st.sidebar:
    st.header("🎯 사용 가이드")
    st.markdown("""
    1. 일반 문구를 입력하세요
    2. 시디즈 톤으로 변환된 결과를 확인하세요
    3. 만족도를 👍/👎로 평가해주세요
    """)
    
    st.markdown("---")
    
    st.markdown("#### 💬 예시")
    st.code("편안한 의자입니다", language=None)
    st.markdown("↓")
    st.info("인체공학적 설계를 통해 누구나 편안하게 사용할 수 있는 시팅 솔루션입니다")
    
    st.markdown("---")
    
    # 피드백 통계
    if st.session_state.feedback_data:
        st.subheader("📊 피드백 통계")
        thumbs_up = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 1)
        thumbs_down = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 0)
        total = thumbs_up + thumbs_down
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👍 긍정", thumbs_up)
        with col2:
            st.metric("👎 부정", thumbs_down)
        
        if total > 0:
            satisfaction = (thumbs_up / total) * 100
            st.progress(satisfaction / 100)
            st.caption(f"만족도: {satisfaction:.1f}%")
    
    st.markdown("---")
    
    if st.button("🗑️ 대화 내역 초기화"):
        st.session_state.messages = []
        st.session_state.feedback_data = {}
        st.session_state.feedback_saved = set()
        st.rerun()
    
    # 관리자 기능
    st.markdown("---")
    st.markdown("#### 🔧 관리자 도구")
    
    if st.button("📥 피드백 데이터 다운로드"):
        if st.session_state.feedback_data:
            # DataFrame 생성
            feedback_list = []
            for idx, data in st.session_state.feedback_data.items():
                feedback_list.append({
                    "시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "원본": data["prompt"],
                    "변환": data["message"],
                    "피드백": "👍" if data["feedback"] == 1 else "👎",
                    "피드백값": data["feedback"]
                })
            
            df = pd.DataFrame(feedback_list)
            
            # CSV 다운로드
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📄 CSV 다운로드",
                data=csv,
                file_name=f"ux_feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("저장된 피드백이 없습니다.")

# ==========================================
# 8. 초기 안내 메시지
# ==========================================
if len(st.session_state.messages) == 0:
    st.info("👇 **아래 입력창에 일반 문구를 입력하면 시디즈 브랜드 톤으로 변환해드립니다!**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📝 Before")
        st.code("편안한 의자입니다")
    
    with col2:
        st.markdown("### ➡️")
        st.markdown("")
    
    with col3:
        st.markdown("### ✨ After")
        st.success("인체공학적 설계를 통해 누구나 편안하게 사용할 수 있는 시팅 솔루션입니다")

# ==========================================
# 9. 대화 내역 표시
# ==========================================
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if message["role"] == "assistant" and i == len(st.session_state.messages) - 1:
            feedback = st.feedback("thumbs", key=f"feedback_{i}")
            
            if feedback is not None and i not in st.session_state.feedback_saved:
                # 세션에 저장
                st.session_state.feedback_data[i] = {
                    "message": message["content"],
                    "feedback": feedback,
                    "prompt": st.session_state.messages[i-1]["content"] if i > 0 else ""
                }
                
                # Google Sheets에 저장
                original = st.session_state.messages[i-1]["content"] if i > 0 else ""
                converted = message["content"]
                
                if save_feedback_to_sheet(original, converted, feedback):
                    st.success("✅ 피드백이 저장되었습니다!")
                    st.session_state.feedback_saved.add(i)
                else:
                    st.warning("⚠️ 피드백 저장 실패 (로컬에는 저장됨)")

# ==========================================
# 10. 사용자 입력 처리
# ==========================================
st.markdown("---")
st.markdown("### 💬 문구를 입력하세요")

prompt = st.chat_input("예: 편안한 의자입니다", key="main_input")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        try:
            model = get_gemini_model()
            full_prompt = f"{SYSTEM_INSTRUCTION}\n\n사용자 요청: {prompt}"
            
            with st.spinner("시디즈 톤으로 변환 중..."):
                response = model.generate_content(full_prompt)
                assistant_message = response.text
            
            st.markdown(assistant_message)
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})
            
        except Exception as e:
            error_str = str(e)
            
            if "429" in error_str or "quota" in error_str.lower():
                st.error("⏱️ **Gemini API 할당량 초과**")
                st.warning("잠시 후 다시 시도해주세요.")
            else:
                st.error(f"❌ 오류: {error_str}")
            
            error_message = "일시적으로 서비스를 사용할 수 없습니다."
            st.session_state.messages.append({"role": "assistant", "content": error_message})
    
    st.rerun()
```

**이제 다음 단계를 진행하세요:**

## ✅ Google Sheets 설정

1. **새 스프레드시트 생성**
   - Google Sheets 접속
   - 새 스프레드시트 생성
   - 이름: "SIDIZ UX 피드백"

2. **헤더 행 추가** (첫 번째 행에)
```
   시간 | 원본 문구 | 변환된 문구 | 피드백 | 피드백값
