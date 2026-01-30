import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(page_title="시디즈 UX 번역기", page_icon="💺", layout="wide")

# ==========================================
# 2. 보안 설정
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=GOOGLE_API_KEY)
    
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    
    st.success(f"✅ 모델 로드 완료: {target}")
    
except KeyError:
    st.error("❌ Secrets에 'gemini.api_key'가 설정되지 않았습니다.")
    st.stop()
except Exception as e:
    st.error(f"❌ Gemini API 초기화 오류: {e}")
    st.stop()

# ==========================================
# 3. 브랜드 가이드라인
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
# 4. 모델 초기화
# ==========================================
@st.cache_resource
def get_gemini_model():
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    return genai.GenerativeModel(target)

# ==========================================
# 5. UI 구성
# ==========================================
st.title("💺 시디즈 UX 라이팅 번역기")
st.markdown("---")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback_data" not in st.session_state:
    st.session_state.feedback_data = {}

# ==========================================
# 6. 사이드바
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
    
    if st.button("🗑️ 대화 내역 초기화"):
        st.session_state.messages = []
        st.session_state.feedback_data = {}
        st.rerun()
    
    if st.session_state.feedback_data:
        st.divider()
        st.subheader("📊 피드백 통계")
        thumbs_up = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 1)
        thumbs_down = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 0)
        st.metric("긍정", thumbs_up)
        st.metric("부정", thumbs_down)

# ==========================================
# 7. 초기 안내 메시지 (대화 기록이 없을 때만)
# ==========================================
if len(st.session_state.messages) == 0:
    st.info("👇 **아래 입력창에 일반 문구를 입력하면 시디즈 브랜드 톤으로 변환해드립니다!**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📝 Before")
        st.code("편안한 의자입니다")
    
    with col2:
        st.markdown("### ➡️")
    
    with col3:
        st.markdown("### ✨ After")
        st.success("인체공학적 설계를 통해 누구나 편안하게 사용할 수 있는 시팅 솔루션입니다")

# ==========================================
# 8. 대화 내역 표시
# ==========================================
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if message["role"] == "assistant" and i == len(st.session_state.messages) - 1:
            feedback = st.feedback("thumbs", key=f"feedback_{i}")
            
            if feedback is not None:
                st.session_state.feedback_data[i] = {
                    "message": message["content"],
                    "feedback": feedback,
                    "prompt": st.session_state.messages[i-1]["content"] if i > 0 else ""
                }

# ==========================================
# 9. 사용자 입력 처리
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
