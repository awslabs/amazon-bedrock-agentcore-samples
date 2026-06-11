import streamlit as st


def apply_custom_styles():
    """Apply custom CSS styles to the Streamlit app"""
    st.markdown(
        """
        <style>
        body {
            background: #181c24 !important;
        }
        .stApp {
            background: #181c24 !important;
        }
        .css-1v0mbdj, .css-1dp5vir {
            border-radius: 14px !important;
            padding: 0.5rem 1rem !important;
        }
        .user-bubble {
            background: #23272f;
            color: #e6e6e6;
            border-radius: 16px;
            padding: 0.7rem 1.2rem;
            margin-bottom: 0.5rem;
            display: inline-block;
            border: 1px solid #3a3f4b;
        }
        .assistant-bubble {
            background: #0b2545;
            color: #e6e6e6;
            border-radius: 16px;
            padding: 0.7rem 1.2rem;
            margin-bottom: 0.5rem;
            display: block;
            border: 1px solid #298dff;
            animation: fadeInUp 0.3s ease-out;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-width: 100%;
        }
        .assistant-bubble.streaming {
            border: 1px solid #4fc3f7;
            box-shadow: 0 0 10px rgba(79, 195, 247, 0.3);
            animation: pulse-border 2s infinite, fadeInUp 0.3s ease-out;
        }
        .thinking-bubble {
            background: #0b2545;
            color: #e6e6e6;
            border-radius: 16px;
            padding: 0.7rem 1.2rem;
            margin-bottom: 0.5rem;
            display: inline-block;
            border: 1px solid #298dff;
            animation: thinking-pulse 1.5s infinite, fadeInUp 0.3s ease-out;
        }
        .typing-cursor::after {
            content: '▋';
            color: #4fc3f7;
            animation: cursor-blink 1s infinite;
            margin-left: 2px;
        }
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes pulse-border {
            0%, 100% {
                border-color: #298dff;
                box-shadow: 0 0 5px rgba(41, 141, 255, 0.3);
            }
            50% {
                border-color: #4fc3f7;
                box-shadow: 0 0 15px rgba(79, 195, 247, 0.6);
            }
        }
        @keyframes thinking-pulse {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
            }
            50% {
                opacity: 0.8;
                transform: scale(1.02);
            }
        }
        @keyframes cursor-blink {
            0%, 50% {
                opacity: 1;
            }
            51%, 100% {
                opacity: 0;
            }
        }
        @keyframes slideInLeft {
            from {
                opacity: 0;
                transform: translateX(-30px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        .sidebar .sidebar-content {
            background: #181c24 !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, .css-10trblm, .css-1cpxqw2 {
            color: #e6e6e6 !important;
        }
        hr {
            border: 1px solid #298dff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
