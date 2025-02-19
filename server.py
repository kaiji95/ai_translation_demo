from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from translation_agent import run_agent
import os
from werkzeug.utils import secure_filename
import PyPDF2
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.units import inch
from PIL import Image
import io
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
CORS(app)

# 配置上传文件夹
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 注册中文字体
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    try:
        data = request.json
        command = data.get('command')
        
        if not command:
            return jsonify({'error': '缺少命令参数'}), 400
        
        # 执行翻译代理
        result = run_agent(command)
        
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/translate-pdf', methods=['POST'])
def translate_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件被上传'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        source_lang = request.form.get('source_lang', 'en')
        target_lang = request.form.get('target_lang', 'zh')
        user_reflection = request.form.get('user_reflection', '')
        
        # 保存上传的文件
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # 读取PDF内容
            pdf_text = ""
            pdf_reader = PyPDF2.PdfReader(filepath)
            
            # 获取所有页面的文本和图片
            pages_content = []
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                # 存储页面内容
                pages_content.append({
                    'text': text,
                    'images': []
                })
                
                # 提取图片
                if '/Resources' in page and '/XObject' in page['/Resources']:
                    xObject = page['/Resources']['/XObject'].get_object()
                    for obj in xObject:
                        if xObject[obj]['/Subtype'] == '/Image':
                            image = xObject[obj]
                            # 获取图片数据
                            try:
                                if image['/Filter'] == '/DCTDecode':
                                    img_data = image._data
                                    ext = '.jpg'
                                elif image['/Filter'] == '/FlateDecode':
                                    img_data = image._data
                                    ext = '.png'
                                elif image['/Filter'] == '/JPXDecode':
                                    img_data = image._data
                                    ext = '.jp2'
                                else:
                                    continue
                                
                                # 保存图片信息
                                pages_content[-1]['images'].append({
                                    'data': img_data,
                                    'extension': ext
                                })
                            except:
                                continue
            
            # 收集所有文本进行翻译
            all_text = "\n".join(page['text'] for page in pages_content)
            
            # 翻译文本
            translation_command = f"""
                1. 调用 initial_translation 将 "{all_text}" 从 {source_lang} 翻译成 {target_lang}。
                2. 调用 reflection_translation 并传入用户建议 "{user_reflection}", 生成相应建议。
                3. 调用 enhance_translation 并得到最终的翻译结果。
            """
            translated_text = run_agent(translation_command)
            
            # 将翻译结果分割成段落
            translated_paragraphs = translated_text.split('\n')
            
            # 创建新的PDF
            output_buffer = BytesIO()
            c = canvas.Canvas(output_buffer, pagesize=A4)
            width, height = A4
            
            # 创建样式
            styles = getSampleStyleSheet()
            chinese_style = ParagraphStyle(
                'ChineseStyle',
                parent=styles['Normal'],
                fontName='STSong-Light',
                fontSize=12,
                leading=14,
                wordWrap='CJK'
            )
            
            current_y = height - inch
            current_para = 0
            
            # 处理每个段落和图片
            for page_num, page_content in enumerate(pages_content):
                if current_para >= len(translated_paragraphs):
                    break
                
                # 添加文本
                while current_para < len(translated_paragraphs):
                    if current_y < inch:  # 如果页面空间不足
                        c.showPage()  # 创建新页面
                        current_y = height - inch
                        c.setFont('STSong-Light', 12)
                    
                    para = Paragraph(translated_paragraphs[current_para], chinese_style)
                    w, h = para.wrap(width - 2*inch, height)  # 留出页边距
                    
                    if current_y - h < inch:  # 如果当前段落放不下
                        c.showPage()
                        current_y = height - inch
                        c.setFont('STSong-Light', 12)
                    
                    para.drawOn(c, inch, current_y - h)
                    current_y -= h + 12  # 段落间距
                    current_para += 1
                
                # 添加图片
                for img_info in page_content['images']:
                    if current_y < inch + 100:  # 为图片预留更多空间
                        c.showPage()
                        current_y = height - inch
                    
                    try:
                        img = Image.open(io.BytesIO(img_info['data']))
                        img_width, img_height = img.size
                        
                        # 计算图片的缩放比例
                        aspect = img_width / float(img_height)
                        if img_width > width - 2*inch:
                            img_width = width - 2*inch
                            img_height = img_width / aspect
                        
                        # 绘制图片
                        c.drawImage(
                            ImageReader(img),
                            inch,
                            current_y - img_height,
                            width=img_width,
                            height=img_height
                        )
                        current_y -= img_height + 12
                    except Exception as img_error:
                        print(f"Image processing error: {img_error}")
                        continue
                
                # 创建新页面
                if page_num < len(pages_content) - 1:
                    c.showPage()
                    current_y = height - inch
                    c.setFont('STSong-Light', 12)
            
            # 保存PDF
            c.save()
            
            # 准备响应
            output_buffer.seek(0)
            return send_file(
                output_buffer,
                as_attachment=True,
                download_name=f"translated_{filename}",
                mimetype='application/pdf'
            )
            
        finally:
            # 清理临时文件
            if os.path.exists(filepath):
                os.remove(filepath)
                
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("Error details:", error_details)
        return jsonify({'error': str(e), 'details': error_details}), 500

if __name__ == '__main__':
    app.run(debug=True)
