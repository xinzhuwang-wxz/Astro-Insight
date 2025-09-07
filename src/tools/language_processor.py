#!/usr/bin/env python3
"""
语言检测和翻译功能模块
提供多语言支持和天体名称提取功能
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

try:
    from langdetect import detect, DetectorFactory

    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    logging.warning("langdetect库未安装，将使用简单的语言检测")

try:
    from deep_translator import GoogleTranslator
    DEEP_TRANSLATOR_AVAILABLE = True
except ImportError:
    DEEP_TRANSLATOR_AVAILABLE = False
    logging.warning("deep_translator库不可用，将尝试备用翻译库")

try:
    from google_trans_new import google_translator
    GOOGLE_TRANS_NEW_AVAILABLE = True
except ImportError:
    GOOGLE_TRANS_NEW_AVAILABLE = False
    logging.warning("google-trans-new库未安装，将使用简单的翻译功能")

# 百度翻译
try:
    import translators as ts
    TRANSLATORS_AVAILABLE = True
except ImportError:
    TRANSLATORS_AVAILABLE = False
    logging.warning("translators库未安装，将跳过百度翻译等服务")

# 微软翻译
try:
    from azure.cognitiveservices.language.translator import TranslatorTextClient
    from azure.cognitiveservices.language.translator.models import TranslatorTextClientConfiguration
    AZURE_TRANSLATOR_AVAILABLE = True
except ImportError:
    AZURE_TRANSLATOR_AVAILABLE = False
    logging.warning("azure翻译库未安装，将跳过微软翻译服务")

# 腾讯翻译
try:
    from tencentcloud.common import credential
    from tencentcloud.tmt.v20180321 import tmt_client, models
    TENCENT_TRANSLATOR_AVAILABLE = True
except ImportError:
    TENCENT_TRANSLATOR_AVAILABLE = False
    logging.warning("腾讯云SDK未安装，将跳过腾讯翻译服务")

# 阿里翻译
try:
    from alibabacloud_alimt20181012.client import Client as AliMTClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_alimt20181012 import models as alimt_models
    ALIBABA_TRANSLATOR_AVAILABLE = True
except ImportError:
    ALIBABA_TRANSLATOR_AVAILABLE = False
    logging.warning("阿里云翻译SDK未安装，将跳过阿里翻译服务")

# 环境变量支持
import os

# 设置langdetect的随机种子以获得一致的结果
if LANGDETECT_AVAILABLE:
    DetectorFactory.seed = 0

logger = logging.getLogger(__name__)


@dataclass
class LanguageDetectionResult:
    """语言检测结果"""

    language: str
    confidence: float
    original_text: str
    detected_method: str


@dataclass
class TranslationResult:
    """翻译结果"""

    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence: float
    translation_method: str


@dataclass
class CelestialObjectExtraction:
    """天体对象提取结果"""

    object_name: str
    object_type: Optional[str]
    coordinates: Optional[Dict[str, float]]
    confidence: float
    extraction_method: str
    alternative_names: List[str]


class LanguageProcessor:
    """语言处理器类"""

    def __init__(self):
        # 翻译器实例
        self.translator = None
        self.backup_translator = None
        self.azure_translator = None
        self.tencent_translator = None
        self.alibaba_translator = None
        
        # 翻译源配置
        self.translation_sources = []
        self._init_translation_sources()
        
        # 尝试初始化主要的Google翻译器
        if DEEP_TRANSLATOR_AVAILABLE:
            try:
                self.translator = GoogleTranslator
                self.translation_sources.append({
                    'name': 'deep_translator_google',
                    'instance': self.translator,
                    'method': self._translate_with_google,
                    'priority': 1
                })
            except Exception as e:
                logger.warning(f"初始化Deep Translator失败: {e}")
        
        # 尝试初始化备用翻译器
        if GOOGLE_TRANS_NEW_AVAILABLE:
            try:
                self.backup_translator = google_translator()
                self.translation_sources.append({
                    'name': 'google_translate_new',
                    'instance': self.backup_translator,
                    'method': self._translate_with_google_new,
                    'priority': 2
                })
            except Exception as e:
                logger.warning(f"初始化备用翻译器失败: {e}")
        
        # 初始化其他翻译源
        self._init_other_translators()
        
        # 按优先级排序翻译源
        self.translation_sources.sort(key=lambda x: x['priority'])
        
        
    
    def _init_translation_sources(self):
        """初始化翻译源配置"""
        # 从环境变量读取API密钥
        self.baidu_app_id = os.getenv('BAIDU_TRANSLATE_APP_ID')
        self.baidu_secret_key = os.getenv('BAIDU_TRANSLATE_SECRET_KEY')
        self.azure_key = os.getenv('AZURE_TRANSLATOR_KEY')
        self.azure_region = os.getenv('AZURE_TRANSLATOR_REGION', 'global')
        self.tencent_secret_id = os.getenv('TENCENT_SECRET_ID')
        self.tencent_secret_key = os.getenv('TENCENT_SECRET_KEY')
        self.alibaba_access_key_id = os.getenv('ALIBABA_ACCESS_KEY_ID')
        self.alibaba_access_key_secret = os.getenv('ALIBABA_ACCESS_KEY_SECRET')
    
    def _init_other_translators(self):
        """初始化其他翻译服务"""
        # 有道翻译（通过translators库）
        if TRANSLATORS_AVAILABLE:
            self.translation_sources.append({
                'name': 'youdao_translate',
                'instance': None,
                'method': self._translate_with_youdao,
                'priority': 3
            })
        
        # 百度翻译暂时不可用（需要认证）
        # if TRANSLATORS_AVAILABLE:
        #     self.translation_sources.append({
        #         'name': 'baidu_translate',
        #         'instance': None,
        #         'method': self._translate_with_baidu,
        #         'priority': 4
        #     })
        
        # 微软翻译
        if AZURE_TRANSLATOR_AVAILABLE and self.azure_key:
            try:
                config = TranslatorTextClientConfiguration(
                    subscription_key=self.azure_key,
                    region=self.azure_region
                )
                self.azure_translator = TranslatorTextClient(config)
                self.translation_sources.append({
                    'name': 'azure_translate',
                    'instance': self.azure_translator,
                    'method': self._translate_with_azure,
                    'priority': 4
                })
            except Exception as e:
                logger.warning(f"初始化Azure翻译器失败: {e}")
        
        # 腾讯翻译
        if TENCENT_TRANSLATOR_AVAILABLE and self.tencent_secret_id and self.tencent_secret_key:
            try:
                cred = credential.Credential(self.tencent_secret_id, self.tencent_secret_key)
                self.tencent_translator = tmt_client.TmtClient(cred, "ap-beijing")
                self.translation_sources.append({
                    'name': 'tencent_translate',
                    'instance': self.tencent_translator,
                    'method': self._translate_with_tencent,
                    'priority': 5
                })
            except Exception as e:
                logger.warning(f"初始化腾讯翻译器失败: {e}")
        
        # 阿里翻译
        if ALIBABA_TRANSLATOR_AVAILABLE and self.alibaba_access_key_id and self.alibaba_access_key_secret:
            try:
                config = open_api_models.Config(
                    access_key_id=self.alibaba_access_key_id,
                    access_key_secret=self.alibaba_access_key_secret
                )
                config.endpoint = 'mt.cn-hangzhou.aliyuncs.com'
                self.alibaba_translator = AliMTClient(config)
                self.translation_sources.append({
                    'name': 'alibaba_translate',
                    'instance': self.alibaba_translator,
                    'method': self._translate_with_alibaba,
                    'priority': 6
                })
            except Exception as e:
                logger.warning(f"初始化阿里翻译器失败: {e}")

        # 天体名称模式
        self.celestial_patterns = {
            "messier": re.compile(r"\b[Mm]\s*\d{1,3}\b"),
            "ngc": re.compile(r"\b[Nn][Gg][Cc]\s*\d{1,5}\b"),
            "ic": re.compile(r"\b[Ii][Cc]\s*\d{1,5}\b"),
            "hd": re.compile(r"\b[Hh][Dd]\s*\d{1,6}\b"),
            "hr": re.compile(r"\b[Hh][Rr]\s*\d{1,5}\b"),
            "hip": re.compile(r"\b[Hh][Ii][Pp]\s*\d{1,6}\b"),
            "common_names": re.compile(
                r"\b(?:仙女座星系|猎户座大星云|太阳|月亮|地球|火星|金星|木星|土星|天王星|海王星|冥王星|仙女座|"
                + r"Andromeda Galaxy|Orion Nebula|Sun|Moon|Earth|Mars|Venus|Jupiter|Saturn|Uranus|Neptune|Pluto|"
                + r"Sirius|Vega|Polaris|Betelgeuse|Rigel|Aldebaran|Antares|"
                + r"Andromeda|Orion|Cassiopeia|Ursa Major|Ursa Minor)\b",
                re.IGNORECASE,
            ),
        }

        # 中英文天体名称映射（扩展版）
        self.celestial_name_mapping = {
            # 星系
            '仙女座星系': 'Andromeda Galaxy',
            '银河系': 'Milky Way',
            '大麦哲伦云': 'Large Magellanic Cloud',
            '小麦哲伦云': 'Small Magellanic Cloud',
            '三角座星系': 'Triangulum Galaxy',
            '室女座星系团': 'Virgo Cluster',
            '漩涡星系': 'Whirlpool Galaxy',
            '草帽星系': 'Sombrero Galaxy',
            
            # 行星
            '太阳': 'Sun',
            '月球': 'Moon',
            '月亮': 'Moon',
            '水星': 'Mercury',
            '金星': 'Venus',
            '地球': 'Earth',
            '火星': 'Mars',
            '木星': 'Jupiter',
            '土星': 'Saturn',
            '天王星': 'Uranus',
            '海王星': 'Neptune',
            '冥王星': 'Pluto',
            
            # 恒星
            '北极星': 'Polaris',
            '织女星': 'Vega',
            '天狼星': 'Sirius',
            '参宿四': 'Betelgeuse',
            '参宿七': 'Rigel',
            '南河三': 'Procyon',
            '老人星': 'Canopus',
            '大角星': 'Arcturus',
            '五车二': 'Capella',
            '心宿二': 'Antares',
            '牛郎星': 'Altair',
            '轩辕十四': 'Regulus',
            '角宿一': 'Spica',
            '毕宿五': 'Aldebaran',
            
            # 星座
            '仙女座': 'Andromeda',
            '大熊座': 'Ursa Major',
            '小熊座': 'Ursa Minor',
            '猎户座': 'Orion',
            '天鹅座': 'Cygnus',
            '天琴座': 'Lyra',
            '天鹰座': 'Aquila',
            '双子座': 'Gemini',
            '狮子座': 'Leo',
            '处女座': 'Virgo',
            '天秤座': 'Libra',
            '天蝎座': 'Scorpius',
            '射手座': 'Sagittarius',
            '摩羯座': 'Capricornus',
            '水瓶座': 'Aquarius',
            '双鱼座': 'Pisces',
            '白羊座': 'Aries',
            '金牛座': 'Taurus',
            '巨蟹座': 'Cancer',
            '仙后座': 'Cassiopeia',
            '大犬座': 'Canis Major',
            '小犬座': 'Canis Minor',
            '英仙座': 'Perseus',
            '御夫座': 'Auriga',
            '牧夫座': 'Boötes',
            '天龙座': 'Draco',
            '仙王座': 'Cepheus',
            
            # 星云和星团
            '猎户座大星云': 'Orion Nebula',
            '马头星云': 'Horsehead Nebula',
            '蟹状星云': 'Crab Nebula',
            '玫瑰星云': 'Rosette Nebula',
            '昴宿星团': 'Pleiades',
            '毕宿星团': 'Hyades',
            '鹰状星云': 'Eagle Nebula',
            '猫眼星云': 'Cat\'s Eye Nebula',
            '环状星云': 'Ring Nebula',
            '螺旋星云': 'Helix Nebula',
            '北美洲星云': 'North America Nebula',
            '火焰星云': 'Flame Nebula',
            '蜂巢星团': 'Beehive Cluster',
            '双重星团': 'Double Cluster',
            '球状星团M13': 'Hercules Globular Cluster'
        }
        
        # 保持向后兼容性
        self.name_mapping = self.celestial_name_mapping

        # 天体类型关键词
        self.object_type_keywords = {
            "star": ["恒星", "星", "star", "stellar"],
            "planet": ["行星", "planet", "planetary"],
            "galaxy": ["星系", "galaxy", "galactic"],
            "nebula": ["星云", "nebula"],
            "cluster": ["星团", "cluster"],
            "comet": ["彗星", "comet"],
            "asteroid": ["小行星", "asteroid"],
            "moon": ["卫星", "moon", "satellite"],
        }

    def detect_language(self, text: str) -> LanguageDetectionResult:
        """检测文本语言"""
        if not text or not text.strip():
            return LanguageDetectionResult(
                language="unknown",
                confidence=0.0,
                original_text=text,
                detected_method="empty_text",
            )

        # 优先使用规则检测中文，因为langdetect对中文识别不准确
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        total_chars = len(text.replace(" ", ""))

        if total_chars == 0:
            return LanguageDetectionResult(
                language="unknown",
                confidence=0.0,
                original_text=text,
                detected_method="rule_based",
            )

        chinese_ratio = chinese_chars / total_chars

        # 如果包含中文字符，优先识别为中文
        if chinese_ratio > 0.1:  # 降低阈值，更容易识别中文
            return LanguageDetectionResult(
                language="zh",
                confidence=min(chinese_ratio * 2, 1.0),
                original_text=text,
                detected_method="rule_based",
            )

        # 如果没有中文字符，再尝试使用langdetect
        if LANGDETECT_AVAILABLE:
            try:
                detected_lang = detect(text)
                confidence = 0.8  # langdetect不提供置信度，使用默认值
                return LanguageDetectionResult(
                    language=detected_lang,
                    confidence=confidence,
                    original_text=text,
                    detected_method="langdetect",
                )
            except Exception as e:
                logger.warning(f"langdetect检测失败: {e}")

        # 默认为英文
        return LanguageDetectionResult(
            language="en",
            confidence=0.5,
            original_text=text,
            detected_method="rule_based",
        )

    def translate_text(
        self, text: str, target_language: str = "en", source_language: str = "auto"
    ) -> TranslationResult:
        """翻译文本 - 使用多翻译源故障转移机制"""
        if not text or not text.strip():
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language="unknown",
                target_language=target_language,
                confidence=0.0,
                translation_method="no_translation",
            )

        # 检测源语言
        if source_language == "auto":
            detection_result = self.detect_language(text)
            source_language = detection_result.language

        # 如果源语言和目标语言相同，直接返回
        if source_language == target_language:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
                confidence=1.0,
                translation_method="no_translation_needed",
            )

        # 按优先级尝试各个翻译源
        for source in self.translation_sources:
            try:
                result = source['method'](text, source_language, target_language)
                if result and result != text:
                    logger.info(f"使用 {source['name']} 翻译成功")
                    return TranslationResult(
                        original_text=text,
                        translated_text=result,
                        source_language=source_language,
                        target_language=target_language,
                        confidence=0.8,
                        translation_method=source['name'],
                    )
            except Exception as e:
                logger.warning(f"{source['name']} 翻译失败: {e}")
                continue

        # 如果所有翻译器都失败，尝试简单的词典翻译
        logger.info("所有翻译源失败，使用简单词典翻译")
        translated_text = self._simple_translate(text, source_language, target_language)

        return TranslationResult(
            original_text=text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            confidence=0.6 if translated_text != text else 0.0,
            translation_method="simple_dictionary",
        )
    
    def _translate_with_google(self, text, source_lang, target_lang):
        """使用Deep Translator (Google翻译)"""
        if not self.translator:
            raise Exception("Deep Translator未初始化")
        
        # 确保语言代码有效，deep_translator使用标准语言代码格式
        lang_mapping = {
            'zh': 'zh',
            'en': 'en',
            'ja': 'ja',
            'ko': 'ko',
            'fr': 'fr',
            'de': 'de',
            'es': 'es',
            'ru': 'ru'
        }
        valid_source_lang = lang_mapping.get(source_lang, 'auto')
        valid_target_lang = lang_mapping.get(target_lang, target_lang)
        
        # 使用deep_translator的GoogleTranslator
        translator = self.translator(source=valid_source_lang, target=valid_target_lang)
        result = translator.translate(text)
        return result
    
    def _translate_with_google_new(self, text, source_lang, target_lang):
        """使用Google翻译新版"""
        if not self.backup_translator:
            raise Exception("Google翻译新版未初始化")
        
        # google-trans-new使用不同的语言代码格式
        lang_mapping_new = {
            'zh': 'zh',
            'en': 'en',
            'ja': 'ja',
            'ko': 'ko',
            'fr': 'fr',
            'de': 'de',
            'es': 'es',
            'ru': 'ru'
        }
        valid_source_lang = lang_mapping_new.get(source_lang, 'auto')
        valid_target_lang = lang_mapping_new.get(target_lang, target_lang)
        
        result = self.backup_translator.translate(
            text, lang_tgt=valid_target_lang, lang_src=valid_source_lang
        )
        return result
    
    def _translate_with_baidu(self, text, source_lang, target_lang):
        """使用百度翻译"""
        if not TRANSLATORS_AVAILABLE:
            raise Exception("translators库不可用")
        
        # 语言代码映射
        lang_map = {
            'zh': 'zh',
            'en': 'en',
            'zh-cn': 'zh',
            'zh-tw': 'cht'
        }
        
        src_lang = lang_map.get(source_lang, source_lang)
        tgt_lang = lang_map.get(target_lang, target_lang)
        
        import translators as ts
        result = ts.translate_text(text, translator='baidu', from_language=src_lang, to_language=tgt_lang)
        return result
    
    def _translate_with_youdao(self, text, source_lang, target_lang):
        """使用有道翻译"""
        if not TRANSLATORS_AVAILABLE:
            raise Exception("translators库不可用")
        
        # 语言代码映射
        lang_map = {
            'zh': 'zh-CHS',
            'en': 'en',
            'zh-cn': 'zh-CHS',
            'zh-tw': 'zh-CHT'
        }
        
        src_lang = lang_map.get(source_lang, source_lang)
        tgt_lang = lang_map.get(target_lang, target_lang)
        
        import translators as ts
        result = ts.translate_text(text, translator='youdao', from_language=src_lang, to_language=tgt_lang)
        return result
    
    def _translate_with_azure(self, text, source_lang, target_lang):
        """使用微软Azure翻译"""
        if not self.azure_translator:
            raise Exception("Azure翻译器未初始化")
        
        # 语言代码映射
        lang_map = {
            'zh': 'zh-Hans',
            'zh-cn': 'zh-Hans',
            'zh-tw': 'zh-Hant',
            'en': 'en'
        }
        
        tgt_lang = lang_map.get(target_lang, target_lang)
        
        # 注意：这里需要根据实际的Azure SDK API调整
        # 由于Azure SDK的具体实现可能不同，这里提供一个基本框架
        raise Exception("Azure翻译实现需要根据具体SDK调整")
    
    def _translate_with_tencent(self, text, source_lang, target_lang):
        """使用腾讯翻译"""
        if not self.tencent_translator:
            raise Exception("腾讯翻译器未初始化")
        
        # 语言代码映射
        lang_map = {
            'zh': 'zh',
            'zh-cn': 'zh',
            'en': 'en'
        }
        
        src_lang = lang_map.get(source_lang, source_lang)
        tgt_lang = lang_map.get(target_lang, target_lang)
        
        req = tmt_models.TextTranslateRequest()
        req.SourceText = text
        req.Source = src_lang
        req.Target = tgt_lang
        req.ProjectId = 0
        
        resp = self.tencent_translator.TextTranslate(req)
        return resp.TargetText
    
    def _translate_with_alibaba(self, text, source_lang, target_lang):
        """使用阿里翻译"""
        if not self.alibaba_translator:
            raise Exception("阿里翻译器未初始化")
        
        # 语言代码映射
        lang_map = {
            'zh': 'zh',
            'zh-cn': 'zh',
            'en': 'en'
        }
        
        src_lang = lang_map.get(source_lang, source_lang)
        tgt_lang = lang_map.get(target_lang, target_lang)
        
        translate_general_request = alimt_models.TranslateGeneralRequest(
            format_type='text',
            source_language=src_lang,
            target_language=tgt_lang,
            source_text=text,
            scene='general'
        )
        
        response = self.alibaba_translator.translate_general(translate_general_request)
        if response.body and response.body.data:
            return response.body.data.translated
        raise Exception("阿里翻译返回空结果")

    def _simple_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """简单的词典翻译"""
        translated_text = text
        translation_found = False
        
        if source_lang == "zh" and target_lang == "en":
            # 中文到英文 - 按长度排序，优先匹配更长的名称
            sorted_mapping = sorted(self.celestial_name_mapping.items(), 
                                  key=lambda x: len(x[0]), reverse=True)
            for zh_name, en_name in sorted_mapping:
                if zh_name in translated_text:
                    translated_text = translated_text.replace(zh_name, en_name)
                    translation_found = True
                    
        elif source_lang == "en" and target_lang == "zh":
            # 英文到中文
            reverse_mapping = {v: k for k, v in self.celestial_name_mapping.items()}
            # 按长度排序，优先匹配更长的名称
            sorted_reverse = sorted(reverse_mapping.items(), 
                                  key=lambda x: len(x[0]), reverse=True)
            for en_name, zh_name in sorted_reverse:
                if en_name.lower() in translated_text.lower():
                    translated_text = re.sub(
                        re.escape(en_name), zh_name, translated_text, flags=re.IGNORECASE
                    )
                    translation_found = True

        return translated_text

    def extract_celestial_object(self, text: str) -> CelestialObjectExtraction:
        """从文本中提取天体对象信息"""
        if not text or not text.strip():
            return CelestialObjectExtraction(
                object_name="",
                object_type=None,
                coordinates=None,
                confidence=0.0,
                extraction_method="empty_text",
                alternative_names=[],
            )

        # 检测语言
        lang_result = self.detect_language(text)

        # 如果是中文，先翻译成英文
        if lang_result.language == "zh":
            translation_result = self.translate_text(text, "en")
            english_text = translation_result.translated_text
        else:
            english_text = text

        # 提取天体名称
        extracted_names = []
        confidence_scores = []

        # 首先尝试从name_mapping中查找完整的天体名称
        # 按照名称长度排序，优先匹配更长的名称
        sorted_mapping = sorted(self.name_mapping.items(), key=lambda x: len(x[0]), reverse=True)
        for zh_name, en_name in sorted_mapping:
            if zh_name in text:
                extracted_names.append(zh_name)
                confidence_scores.append(0.95)
                break  # 找到匹配后立即停止，避免重复匹配
            elif en_name.lower() in text.lower():
                extracted_names.append(en_name)
                confidence_scores.append(0.95)
                break  # 找到匹配后立即停止，避免重复匹配

        # 如果没有找到完整匹配，再使用正则表达式匹配
        if not extracted_names:
            for pattern_name, pattern in self.celestial_patterns.items():
                # 分别在原文和翻译文本中查找
                for search_text in [text, english_text]:
                    matches = pattern.findall(search_text)
                    for match in matches:
                        clean_match = match.strip()
                        if clean_match and clean_match not in extracted_names:
                            extracted_names.append(clean_match)
                            if pattern_name == "common_names":
                                confidence_scores.append(0.9)
                            else:
                                confidence_scores.append(0.8)

        # 确定主要天体名称
        if extracted_names:
            # 选择置信度最高的名称作为主要名称
            if confidence_scores:
                max_confidence_idx = confidence_scores.index(max(confidence_scores))
                main_name = extracted_names[max_confidence_idx]
                confidence = confidence_scores[max_confidence_idx]
            else:
                main_name = extracted_names[0]
                confidence = 0.5
            
            # 其他名称作为备选
            alternative_names = [name for i, name in enumerate(extracted_names) 
                              if i != (max_confidence_idx if confidence_scores else 0)]
        else:
            # 如果没有匹配到任何天体名称，返回原文本但置信度很低
            main_name = text.strip()
            confidence = 0.1
            alternative_names = []

        # 推断天体类型
        object_type = self._infer_object_type(text + " " + english_text)

        # 尝试提取坐标（简单实现）
        coordinates = self._extract_coordinates(text + " " + english_text)

        return CelestialObjectExtraction(
            object_name=main_name,
            object_type=object_type,
            coordinates=coordinates,
            confidence=confidence,
            extraction_method="pattern_matching",
            alternative_names=alternative_names,
        )

    def _infer_object_type(self, text: str) -> Optional[str]:
        """推断天体类型"""
        text_lower = text.lower()
        
        # 特殊的天体名称直接映射
        special_mappings = {
            "仙女座星系": "galaxy",
            "andromeda galaxy": "galaxy",
            "andromeda": "galaxy",
            "猎户座大星云": "nebula",
            "orion nebula": "nebula",
            "太阳": "star",
            "sun": "star",
            "月亮": "moon",
            "moon": "moon",
            "地球": "planet",
            "earth": "planet",
            "火星": "planet",
            "mars": "planet",
            "金星": "planet",
            "venus": "planet",
            "木星": "planet",
            "jupiter": "planet",
            "土星": "planet",
            "saturn": "planet",
        }
        
        # 首先检查特殊映射
        for name, obj_type in special_mappings.items():
            if name in text_lower:
                return obj_type
        
        # 然后使用关键词匹配
        for obj_type, keywords in self.object_type_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return obj_type

        return None

    def _extract_coordinates(self, text: str) -> Optional[Dict[str, float]]:
        """提取坐标信息（简单实现）"""
        # 匹配度分秒格式：例如 "6h 45m 8.9s -16° 42' 58\""
        coord_pattern = re.compile(
            r'(\d{1,2})h\s*(\d{1,2})m\s*([\d.]+)s\s*([+-]?\d{1,2})°\s*(\d{1,2})\'\s*([\d.]+)"'
        )

        match = coord_pattern.search(text)
        if match:
            h, m, s, deg, arcmin, arcsec = match.groups()

            # 转换为十进制度
            ra = (float(h) + float(m) / 60 + float(s) / 3600) * 15  # 时角转度
            dec = float(deg) + float(arcmin) / 60 + float(arcsec) / 3600
            if deg.startswith("-"):
                dec = -abs(dec)

            return {"ra": ra, "dec": dec}

        # 匹配十进制度格式
        decimal_pattern = re.compile(r"([\d.]+)°?\s*([+-][\d.]+)°?")
        match = decimal_pattern.search(text)
        if match:
            ra, dec = match.groups()
            return {"ra": float(ra), "dec": float(dec)}

        return None

    def process_classification_query(self, user_input: str) -> Dict[str, Any]:
        """处理用户分类查询（主要接口函数）"""
        # 语言检测
        lang_result = self.detect_language(user_input)

        # 翻译为英文（如果需要）
        if lang_result.language == "zh":
            translation_result = self.translate_text(user_input, "en")
            english_query = translation_result.translated_text
        else:
            english_query = user_input
            translation_result = None

        # 天体名称提取
        extraction_result = self.extract_celestial_object(user_input)

        return {
            "original_query": user_input,
            "language_detection": {
                "language": lang_result.language,
                "confidence": lang_result.confidence,
                "method": lang_result.detected_method,
            },
            "translation": {
                "english_query": english_query,
                "translation_confidence": translation_result.confidence
                if translation_result
                else 1.0,
                "translation_method": translation_result.translation_method
                if translation_result
                else "no_translation",
            },
            "celestial_object": {
                "name": extraction_result.object_name,
                "type": extraction_result.object_type,
                "coordinates": extraction_result.coordinates,
                "confidence": extraction_result.confidence,
                "alternative_names": extraction_result.alternative_names,
                "extraction_method": extraction_result.extraction_method,
            },
        }


# 全局语言处理器实例
language_processor = LanguageProcessor()


# 便捷函数
def detect_language(text: str) -> LanguageDetectionResult:
    """检测文本语言"""
    return language_processor.detect_language(text)


def translate_to_english(text: str) -> str:
    """翻译文本为英文"""
    result = language_processor.translate_text(text, "en")
    return result.translated_text


def extract_celestial_object(text: str) -> str:
    """提取天体对象名称"""
    result = language_processor.extract_celestial_object(text)
    return result.object_name


def process_classification_query(user_input: str) -> Dict[str, Any]:
    """处理分类查询"""
    return language_processor.process_classification_query(user_input)
