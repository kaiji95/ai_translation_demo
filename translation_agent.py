import os
from smolagents import CodeAgent, LiteLLMModel, tool
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

model = LiteLLMModel(
  "openrouter/anthropic/claude-3.5-sonnet", 
  temperature=0.7,
  api_key=os.getenv("OPEN_ROUTE_KEY")
)

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=os.getenv("OPEN_ROUTE_KEY")
)

def call_llm(prompt, model = 'qwen/qwen-2.5-7b-instruct'):
    completion = client.chat.completions.create(
      extra_body={},
      model='anthropic/claude-3.5-sonnet',
      messages=[
        {
          "role": "user",
          "content": prompt
        }
      ]
    )
    return completion.choices[0].message.content

@tool
def initial_translation(source_text: str, source_lang: str, target_lang: str) -> str:
    """
    将输入的文字初始翻译成对应的语言.

    Args:
        source_text: 要翻译的文字内容.
        source_lang: source_text 的语言.
        target_lang: 要翻译成的语言.

    Returns:
        调用大模型翻译的结果。
    """

    prompt = f"""
      This is an {source_lang} to {target_lang} translation, please provide the {target_lang} translation for this text. Do not provide any explanations or text apart from the translation.
      {source_lang}: {source_text}

      {target_lang}:
    """

    return call_llm(prompt)

@tool
def reflection_translation(source_text: str, source_lang: str, target_lang: str, initial_translation_res: str, user_reflection: str) -> str:
    """
    将输入的文字初始翻译成对应的语言.

    Args:
        source_text: 要翻译的文字内容.
        source_lang: source_text 的语言.
        target_lang: 要翻译成的语言.
        initial_translation_res: 初始翻译的结果.
        user_reflection: 用户给出的提示词建议.

    Returns:
        调用大模型给出的建议列表。
    """

    prompt = f"""
      Your task is to carefully read a source text and a translation from {source_lang} to {target_lang}, and then give constructive criticism and helpful suggestions to improve the translation. \
      {user_reflection}

      The source text and initial translation, delimited by XML tags <SOURCE_TEXT></SOURCE_TEXT> and <TRANSLATION></TRANSLATION>, are as follows:

      <SOURCE_TEXT>
      {source_text}
      </SOURCE_TEXT>

      <TRANSLATION>
      {initial_translation_res}
      </TRANSLATION>

      When writing suggestions, pay attention to whether there are ways to improve the translation's 
      (i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),
      (ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules, and ensuring there are no unnecessary repetitions),
      (iii) style (by ensuring the translations reflect the style of the source text and take into account any cultural context),
      (iv) terminology (by ensuring terminology use is consistent and reflects the source text domain; and by only ensuring you use equivalent idioms {target_lang}.

      Write a list of specific, helpful and constructive suggestions for improving the translation.
      Each suggestion should address one specific part of the translation.
      Output only the suggestions and nothing else.
    """

    return call_llm(prompt, 'anthropic/claude-3.5-sonnet')

@tool
def enhance_translation(source_text: str, source_lang: str, target_lang: str, initial_translation_res: str, reflection_translation_res: str) -> str:
    """
    将输入的文字按照初始翻译和优化建议再次翻译.

    Args:
        source_text: 要翻译的文字内容.
        source_lang: source_text 的语言.
        target_lang: 要翻译成的语言.
        initial_translation_res: 初始翻译的结果.
        reflection_translation_res: llm 大模型给出的文字优化建议.

    Returns:
        调用大模型翻译的结果。
    """
    prompt = f"""
      Your task is to carefully read, then edit, a translation from {source_lang} to {target_lang}, taking into account a list of expert suggestions and constructive criticisms.
      The source text, the initial translation, and the expert linguist suggestions are delimited by XML tags <SOURCE_TEXT></SOURCE_TEXT>, <TRANSLATION></TRANSLATION> and <EXPERT_SUGGESTIONS></EXPERT_SUGGESTIONS> as follows.

      <SOURCE_TEXT>
      {source_text}
      </SOURCE_TEXT>

      <TRANSLATION>
      {initial_translation_res}
      </TRANSLATION>

      <EXPERT_SUGGESTIONS>
      {reflection_translation_res}
      </EXPERT_SUGGESTIONS>

      Please take into account the expert suggestions when editing the translation. Edit the translation by ensuring:
      (i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),
      (ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules and ensuring there are no unnecessary repetitions),
      (iii) style (by ensuring the translations reflect the style of the source text)
      (iv) terminology (inappropriate for context, inconsistent use), or
      (v) other errors.

      Output only the new translation and nothing else.
    """

    return call_llm(prompt, 'anthropic/claude-3.5-sonnet')

agent = CodeAgent(tools=[initial_translation, reflection_translation, enhance_translation], model=model)

# 修改run方法的返回值处理
def run_agent(command: str) -> str:
    result = agent.run(command)
    # 确保返回的是字符串类型
    return str(result) if result is not None else "翻译过程中出现错误"

# 测试用例
if __name__ == "__main__":
    test_command = '将 "I guess it comes down a simple choice. Get busy living or get busy dying" 翻译成中文， 并参考用户建议 "翻译的最终风格和语气应该与中国北京口语风格相符" 生成相应的建议，最后得到相应增强后的翻译结果。'
    print(run_agent(test_command))
