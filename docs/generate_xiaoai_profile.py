# -*- coding: utf-8 -*-
"""
生成小爱(XiaoAi)公司资料文档 - 用于客户管理模块测试
"""

from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import os

def create_xiaoai_profile():
    doc = Document()

    # ============ 样式设置 ============
    style = doc.styles['Normal']
    font = style.font
    font.name = '微软雅黑'
    font.size = Pt(11)

    # ============ 封面标题 ============
    doc.add_paragraph()
    doc.add_paragraph()
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('小爱科技有限公司\n企业资料手册')
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1A, 0x56, 0xDB)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = subtitle.add_run('XiaoAi Technology Co., Ltd.')
    run2.font.size = Pt(16)
    run2.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    doc.add_paragraph()
    info_para = doc.add_paragraph()
    info_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run3 = info_para.add_run('文档版本：V1.0\n编制日期：2026年6月\n文档密级：内部公开')
    run3.font.size = Pt(12)
    run3.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    doc.add_page_break()

    # ============ 目录 ============
    toc_title = doc.add_heading('目录', level=1)
    toc_items = [
        '一、公司概况',
        '二、公司基本信息',
        '三、发展历程',
        '四、核心业务与产品',
        '五、组织架构',
        '六、技术实力与研发能力',
        '七、市场与客户',
        '八、企业文化与价值观',
        '九、合作伙伴与资质认证',
        '十、联系方式',
    ]
    for item in toc_items:
        p = doc.add_paragraph(item)
        p.paragraph_format.space_after = Pt(4)

    doc.add_page_break()

    # ============ 一、公司概况 ============
    doc.add_heading('一、公司概况', level=1)

    doc.add_paragraph(
        '小爱科技有限公司（XiaoAi Technology Co., Ltd.）成立于2019年3月，'
        '是一家专注于人工智能应用与互联网服务的国家高新技术企业。'
        '公司总部位于北京市海淀区中关村科技园区，在上海、深圳、杭州设有分支机构。'
    )
    doc.add_paragraph(
        '小爱科技以"让AI技术服务每一个人"为使命，致力于将前沿的人工智能技术'
        '转化为切实可用的互联网产品与服务。公司核心团队来自百度、阿里巴巴、字节跳动等'
        '头部互联网企业，拥有丰富的AI算法研发和大规模产品落地经验。'
    )
    doc.add_paragraph(
        '截至目前，小爱科技已获得累计超过3亿元人民币的风险投资，投资方包括红杉资本、'
        '高瓴创投、经纬中国等知名机构。公司现有员工450余人，其中研发人员占比超过60%。'
        '2025年度公司营收突破2.5亿元，同比增长85%。'
    )

    # ============ 二、公司基本信息 ============
    doc.add_heading('二、公司基本信息', level=1)

    basic_info = [
        ('公司全称', '小爱科技有限公司'),
        ('英文名称', 'XiaoAi Technology Co., Ltd.'),
        ('统一社会信用代码', '91110108MA01ABCD5X'),
        ('成立日期', '2019年3月15日'),
        ('注册资本', '人民币5,000万元'),
        ('法定代表人', '张明远'),
        ('企业类型', '有限责任公司（自然人投资或控股）'),
        ('所属行业', '互联网/人工智能'),
        ('经营范围', '人工智能应用软件开发；互联网信息服务；大数据技术服务；'
                     '云计算服务；智能硬件研发与销售；技术咨询与转让'),
        ('公司规模', '450-500人'),
        ('公司地址', '北京市海淀区中关村大街1号AI创新大厦12层'),
        ('公司网站', 'www.xiaoai-tech.com'),
    ]

    table = doc.add_table(rows=len(basic_info), cols=2, style='Light Shading Accent 1')
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (key, value) in enumerate(basic_info):
        table.rows[i].cells[0].text = key
        table.rows[i].cells[1].text = value
        # 设置列宽
        table.rows[i].cells[0].width = Cm(4)
        table.rows[i].cells[1].width = Cm(12)

    # ============ 三、发展历程 ============
    doc.add_heading('三、发展历程', level=1)

    milestones = [
        ('2019年3月', '公司在北京中关村正式成立，初始团队15人，获得天使轮融资500万元'),
        ('2019年9月', '推出首款产品"小爱智能客服"AI对话系统，首批企业客户突破100家'),
        ('2020年4月', '完成A轮融资3,000万元（红杉资本领投），团队扩展至80人'),
        ('2020年11月', '发布"小爱智能写作助手"，月活用户突破50万'),
        ('2021年6月', '获评国家高新技术企业，取得多项软件著作权和发明专利'),
        ('2021年12月', '完成B轮融资8,000万元（高瓴创投领投），累计服务企业客户超3,000家'),
        ('2022年5月', '推出"小爱AI营销平台"，整合内容生成、SEO优化、多渠道分发'),
        ('2023年1月', 'ChatGPT热潮下全面升级大语言模型能力，发布"小爱GPT"企业版'),
        ('2023年8月', '完成C轮融资1.5亿元（经纬中国领投），估值突破15亿元'),
        ('2024年3月', '发布AI搜索引擎优化（GEO）自动化平台，填补国内市场空白'),
        ('2024年10月', 'GEO平台客户突破500家，覆盖互联网、金融、教育等12个行业'),
        ('2025年6月', '年度营收突破2.5亿元，员工规模超过450人，获评"中国AI 50强企业"'),
        ('2026年1月', '启动国际化战略，推出东南亚市场版本，完成Pre-IPO轮融资'),
    ]

    table2 = doc.add_table(rows=len(milestones) + 1, cols=2, style='Light Shading Accent 1')
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    table2.rows[0].cells[0].text = '时间'
    table2.rows[0].cells[1].text = '事件'
    for i, (time, event) in enumerate(milestones):
        table2.rows[i + 1].cells[0].text = time
        table2.rows[i + 1].cells[1].text = event
        table2.rows[i + 1].cells[0].width = Cm(3)
        table2.rows[i + 1].cells[1].width = Cm(13)

    # ============ 四、核心业务与产品 ============
    doc.add_heading('四、核心业务与产品', level=1)

    doc.add_heading('4.1 小爱GEO智能优化平台', level=2)
    doc.add_paragraph(
        '公司旗舰产品，提供一站式AI搜索引擎优化（GEO/SEO）解决方案。'
        '平台集成了关键词智能蒸馏、AI内容生成、多平台自动发布、收录效果监测等核心功能。'
    )
    features_geo = [
        '关键词蒸馏引擎：基于大语言模型自动生成高价值关键词和搜索问题变体',
        'AI文章生成：自动产出SEO优化的高质量文章，支持40+平台适配',
        '多平台自动发布：支持知乎、百家号、搜狐、头条号、抖音等40+内容平台',
        '收录监测系统：实时监测豆包、千问、DeepSeek等AI搜索引擎收录情况',
        '知识库管理：基于RAGFlow的智能知识检索，支持企业专属知识库构建',
        '数据分析报表：收录趋势、平台分布、关键词排名等全维度数据分析',
    ]
    for f in features_geo:
        doc.add_paragraph(f, style='List Bullet')

    doc.add_heading('4.2 小爱智能客服系统', level=2)
    doc.add_paragraph(
        '基于自然语言处理和深度学习技术的企业级智能客服解决方案。'
        '支持多轮对话、意图识别、情感分析，可无缝接入企业微信、钉钉、网站等渠道。'
        '累计服务企业客户超过3,000家，平均问题解决率达到92%。'
    )

    doc.add_heading('4.3 小爱智能写作助手', level=2)
    doc.add_paragraph(
        '面向个人和企业的AI写作工具，支持营销文案、新闻稿、产品描述、'
        '社交媒体内容等多种场景的智能写作。月活用户超过80万，日生成内容量超过100万篇。'
    )

    doc.add_heading('4.4 小爱AI营销平台', level=2)
    doc.add_paragraph(
        '整合内容生成、SEO优化、社交媒体管理和广告投放的全方位AI营销工具。'
        '通过大数据分析和AI算法，帮助企业实现精准营销和高效获客。'
    )

    # ============ 五、组织架构 ============
    doc.add_heading('五、组织架构', level=1)

    doc.add_paragraph('公司实行扁平化管理，主要部门包括：')

    departments = [
        ('技术研发中心', '180人，下设AI算法组、后端开发组、前端开发组、测试组、DevOps组'),
        ('产品部', '35人，负责产品规划、需求分析、用户体验设计'),
        ('市场营销部', '50人，下设品牌推广组、渠道销售组、内容营销组'),
        ('客户成功部', '45人，负责客户实施、技术支持、客户培训'),
        ('商务拓展部', '30人，负责战略合作、渠道合作、海外业务拓展'),
        ('运营部', '40人，负责平台运营、数据分析、用户增长'),
        ('综合管理部', '30人，下设人力资源组、财务组、行政组、法务组'),
        ('战略研究院', '20人，负责前沿技术研究、行业标准制定、产学研合作'),
    ]

    for dept_name, dept_desc in departments:
        p = doc.add_paragraph()
        run_bold = p.add_run(f'{dept_name}：')
        run_bold.bold = True
        p.add_run(dept_desc)

    # 核心管理团队
    doc.add_heading('5.1 核心管理团队', level=2)

    executives = [
        ('张明远', '创始人兼CEO', '清华大学计算机博士，前百度AI实验室技术负责人，'
         '拥有15年AI研发经验，曾主导多个亿级用户AI产品'),
        ('李思华', '联合创始人兼CTO', '北京大学人工智能硕士，前字节跳动算法架构师，'
         '专精于NLP和推荐系统，发表顶会论文20余篇'),
        ('王雪琳', '首席运营官COO', '中欧商学院MBA，前阿里巴巴高级运营总监，'
         '拥有12年互联网运营管理经验'),
        ('陈国栋', '首席营销官CMO', '复旦大学传播学硕士，前腾讯市场部总经理，'
         '主导过多个知名品牌营销campaign'),
        ('刘芳芳', '首席财务官CFO', '注册会计师，前普华永道高级审计经理，'
         '主导完成多轮融资和财务体系建设'),
    ]

    table3 = doc.add_table(rows=len(executives) + 1, cols=3, style='Light Shading Accent 1')
    table3.alignment = WD_TABLE_ALIGNMENT.CENTER
    table3.rows[0].cells[0].text = '姓名'
    table3.rows[0].cells[1].text = '职位'
    table3.rows[0].cells[2].text = '简介'
    for i, (name, title_text, bio) in enumerate(executives):
        table3.rows[i + 1].cells[0].text = name
        table3.rows[i + 1].cells[1].text = title_text
        table3.rows[i + 1].cells[2].text = bio

    # ============ 六、技术实力与研发能力 ============
    doc.add_heading('六、技术实力与研发能力', level=1)

    doc.add_heading('6.1 技术栈与基础设施', level=2)
    tech_stack = [
        '大语言模型：基于DeepSeek、GPT-4、文心一言等多模型融合架构',
        '后端技术：Python/FastAPI + PostgreSQL + Redis + Elasticsearch',
        '前端技术：Vue3 + TypeScript + Electron 桌面端 + Web端',
        'AI基础设施：自建GPU集群（A100/H100），总算力超过500 PFLOPS',
        '云服务：阿里云/腾讯云双云架构，保障99.99%服务可用性',
        '工作流引擎：基于n8n构建的自动化工作流系统',
        '知识库：RAGFlow智能文档检索与问答系统',
        '自动化测试：基于Playwright的多平台自动化测试框架',
    ]
    for t in tech_stack:
        doc.add_paragraph(t, style='List Bullet')

    doc.add_heading('6.2 知识产权', level=2)
    ip_items = [
        '发明专利：已授权28项，申请中45项（涵盖NLP、推荐算法、内容生成等领域）',
        '软件著作权：已登记56项',
        '注册商标：已注册12项，包括"小爱科技""XiaoAi""小爱GEO"等',
        '数据安全认证：通过ISO 27001信息安全管理体系认证',
        '隐私保护：通过ISO 27701隐私信息管理体系认证',
    ]
    for ip in ip_items:
        doc.add_paragraph(ip, style='List Bullet')

    # ============ 七、市场与客户 ============
    doc.add_heading('七、市场与客户', level=1)

    doc.add_heading('7.1 目标市场', level=2)
    doc.add_paragraph(
        '小爱科技的核心目标市场为中国互联网行业及需要进行数字化营销的中大型企业。'
        '重点覆盖行业包括：互联网、金融、教育培训、医疗健康、制造业、电子商务等。'
    )

    doc.add_heading('7.2 核心客户案例', level=2)
    clients = [
        ('某头部电商平台', '使用GEO平台优化品牌在AI搜索引擎中的曝光，3个月收录率提升320%'),
        ('某在线教育集团', '通过智能写作助手月产优质内容5,000+篇，获客成本降低45%'),
        ('某金融科技公司', '部署智能客服系统，客户满意度提升28%，人工成本降低60%'),
        ('某新能源汽车品牌', 'AI营销平台助力新品上市，全网曝光量突破3亿次'),
        ('某国际连锁酒店', '多语言AI内容生成，覆盖12个国家市场，预订转化率提升35%'),
    ]
    for client_name, client_result in clients:
        p = doc.add_paragraph()
        run_bold = p.add_run(f'{client_name}：')
        run_bold.bold = True
        p.add_run(client_result)

    doc.add_heading('7.3 市场地位', level=2)
    doc.add_paragraph(
        '根据第三方机构艾瑞咨询2025年报告，小爱科技在AI内容营销领域的市场份额排名第三，'
        '在AI搜索引擎优化（GEO）细分领域排名国内第一。公司先后荣获"中国AI 50强企业"'
        '"北京市专精特新中小企业""中关村高新技术企业TOP100"等荣誉。'
    )

    # ============ 八、企业文化与价值观 ============
    doc.add_heading('八、企业文化与价值观', level=1)

    doc.add_heading('8.1 企业使命', level=2)
    doc.add_paragraph('让AI技术服务每一个人').runs[0].bold = True

    doc.add_heading('8.2 企业愿景', level=2)
    doc.add_paragraph('成为全球领先的AI应用服务平台，让人工智能成为每个企业和个人的得力助手').runs[0].bold = True

    doc.add_heading('8.3 核心价值观', level=2)
    values = [
        ('用户至上', '始终以用户需求为核心，用技术解决真实问题'),
        ('技术创新', '持续探索前沿技术，保持技术领先优势'),
        ('开放协作', '倡导开放包容的团队文化，鼓励跨部门协作'),
        ('追求卓越', '不满足于现状，持续优化每一个细节'),
        ('社会责任', '善用AI技术，推动社会进步和可持续发展'),
    ]
    for v_name, v_desc in values:
        p = doc.add_paragraph()
        run_bold = p.add_run(f'{v_name}：')
        run_bold.bold = True
        p.add_run(v_desc)

    # ============ 九、合作伙伴与资质认证 ============
    doc.add_heading('九、合作伙伴与资质认证', level=1)

    doc.add_heading('9.1 战略合作伙伴', level=2)
    partners = [
        '百度智能云 - AI云服务战略合作伙伴',
        '阿里云 - 云基础设施合作伙伴',
        '华为 - 鲲鹏生态合作伙伴',
        '中国信息通信研究院 - 产学研合作单位',
        '清华大学计算机系 - 联合实验室',
        '北京大学人工智能研究院 - 技术合作单位',
    ]
    for partner in partners:
        doc.add_paragraph(partner, style='List Bullet')

    doc.add_heading('9.2 资质认证', level=2)
    certs = [
        '国家高新技术企业（GR20191100XXXX）',
        'ISO 27001信息安全管理体系认证',
        'ISO 27701隐私信息管理体系认证',
        'ISO 9001质量管理体系认证',
        'CMMI Level 3能力成熟度认证',
        '北京市专精特新中小企业',
        '中关村高新技术企业',
        '软件企业认定证书',
    ]
    for cert in certs:
        doc.add_paragraph(cert, style='List Bullet')

    # ============ 十、联系方式 ============
    doc.add_heading('十、联系方式', level=1)

    contact_info = [
        ('公司名称', '小爱科技有限公司（XiaoAi Technology Co., Ltd.）'),
        ('注册地址', '北京市海淀区中关村大街1号AI创新大厦12层'),
        ('办公地址', '北京市海淀区中关村大街1号AI创新大厦12-15层'),
        ('上海分部', '上海市浦东新区张江高科技园区博云路2号浦软大厦8层'),
        ('深圳分部', '深圳市南山区科技园南区数字大厦6层'),
        ('杭州分部', '杭州市余杭区未来科技城梦想小镇创业大街18号'),
        ('总机电话', '010-8888-6666'),
        ('客服热线', '400-888-9527'),
        ('商务邮箱', 'business@xiaoai-tech.com'),
        ('客服邮箱', 'support@xiaoai-tech.com'),
        ('公司网站', 'https://www.xiaoai-tech.com'),
        ('官方微信', '小爱科技XiaoAi'),
        ('联系人（商务）', '王雪琳 首席运营官'),
        ('联系电话（商务）', '138-0000-1234'),
        ('联系人（技术）', '李思华 首席技术官'),
        ('联系电话（技术）', '139-0000-5678'),
    ]

    table4 = doc.add_table(rows=len(contact_info), cols=2, style='Light Shading Accent 1')
    table4.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (key, value) in enumerate(contact_info):
        table4.rows[i].cells[0].text = key
        table4.rows[i].cells[1].text = value
        table4.rows[i].cells[0].width = Cm(4.5)
        table4.rows[i].cells[1].width = Cm(11.5)

    # ============ 结尾声明 ============
    doc.add_paragraph()
    doc.add_paragraph()
    disclaimer = doc.add_paragraph()
    disclaimer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_disc = disclaimer.add_run(
        '— 本文件为小爱科技有限公司内部资料，未经授权不得对外传播 —\n'
        '© 2026 XiaoAi Technology Co., Ltd. All Rights Reserved.'
    )
    run_disc.font.size = Pt(9)
    run_disc.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # ============ 保存文件 ============
    output_path = os.path.join(os.path.dirname(__file__), '小爱科技公司资料.docx')
    doc.save(output_path)
    print(f'文档已生成: {output_path}')
    return output_path


if __name__ == '__main__':
    path = create_xiaoai_profile()
    print(f'完成！文件大小: {os.path.getsize(path) / 1024:.1f} KB')
