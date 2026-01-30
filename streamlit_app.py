import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 보안 설정 (Secrets에서 키 가져오기)
# ==========================================
try:
    # Streamlit Cloud의 Secrets 설정에서 키를 읽어옵니다.
    GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except KeyError:
    st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다. 관리자 설정을 확인해주세요.")
    st.stop()

# ==========================================
# 2. 브랜드 가이드라인 (System Instruction)
# ==========================================
SYSTEM_INSTRUCTION = """
너는 시디즈(SIDIZ)의 공식 UX 라이터야. 아래 가이드를 엄격히 준수해줘.
1. 말투: 친절하고 세심한 '퍼스널 시팅 코치'.
2. 원칙: 단정적인 명령형보다는 사용자의 경험을 제안하는 권유형 사용.
3. 예시: '로그인하세요' -> '시디즈와 함께 몰입의 시간을 시작해 보세요.'
"""

# ==========================================
# 3. UI 구성 및 채팅 로직
# ==========================================
st.set_page_config(page_title="시디즈 UX 번역기", page_icon="💺")
st.title("💺 시디즈 UX 라이팅 번역기")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 내역 표시 및 피드백 버튼
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and i == len(st.session_state.messages) - 1:
            # 엄지척 피드백 수집
            st.feedback("thumbs", key=f"feedback_{i}")

# 사용자 입력 처리
if prompt := st.chat_input("수정할 문구를 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Gemini 모델 호출 (System Instruction 포함)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_INSTRUCTION
        )
        response = model.generate_content(prompt)
        st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        st.rerun()
