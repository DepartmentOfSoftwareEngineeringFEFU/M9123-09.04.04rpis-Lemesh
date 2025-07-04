from pymorphy3 import MorphAnalyzer
from yargy import Parser, rule, or_, and_
from yargy.predicates import gram, eq, in_, type, caseless, dictionary
from yargy.interpretation import fact
from abc import ABC, abstractmethod
import sqlite3
import ast
import re

class BaseExtractorStrategy(ABC):
    def __init__(self):
        self.morph_analyzer = MorphAnalyzer()
    
    @abstractmethod
    def extract(self, definition):
        pass

    @abstractmethod
    def reconstruct(self, fact_d: dict) -> str:
        pass

# --- Размерные величины ---
class DimensionalExtractor(BaseExtractorStrategy):

    def create_term_rule(self):
        Term = fact('Term', ['name'])
        return rule(
            eq('Объем'),
            eq('понятия'),
            or_(
                rule(
                    gram('NOUN').repeatable()
                ),
                rule(
                    gram('ADJF').repeatable(),
                    gram('NOUN').repeatable()
                )
            ).interpretation(Term.name)
        ).interpretation(Term)

    def create_volume_rule(self):
        ConceptVolume = fact('ConceptVolume', ['sign', 'volume'])
        return rule(
            eq('состоит'),
            eq('из'),
            gram('ADJF').optional().interpretation(ConceptVolume.sign),
            gram('ADJF').interpretation(ConceptVolume.volume),
            gram('NOUN')
        ).interpretation(ConceptVolume)

    def create_clarification_rule(self, is_left=True):
        Clarification = fact(
            'Clarification',
            ['pre_first_relation', 'first_relation', 'term_1', 'pre_second_relation', 'second_relation', 'term_2']
        ) if is_left else fact('Clarification', ['pre_second_relation', 'second_relation', 'term_2'])

        eq_left = eq('элементы') if is_left else eq(',')
        eq_right = eq('которого') if is_left else eq('но')

        first_relation = in_('строго').optional().interpretation(Clarification.pre_first_relation) if is_left else in_('строго').optional().interpretation(Clarification.pre_second_relation)
        second_relation = in_(('больше', 'меньше')).interpretation(Clarification.first_relation) if is_left else in_(('больше', 'меньше')).interpretation(Clarification.second_relation)

        # Добавляем распознавание -∞ и ∞
        infinity_rule = or_(
            rule(eq('-'), eq('∞')),  # минус + бесконечность как два токена
            rule(eq('∞'))
        )

        # Правило для терма, которое может быть либо NOUN, либо INT, либо символом бесконечности
        term_rule = or_(
            rule(gram('NOUN').repeatable()),
            rule(type('INT')),
            infinity_rule
        ).interpretation(Clarification.term_1 if is_left else Clarification.term_2)

        return rule(
            eq_left,
            eq_right,
            or_(
                rule(
                    first_relation,
                    second_relation
                ),
                rule(
                    second_relation,
                    eq('либо'),
                    eq('равны')
                )
            ),
            term_rule
        ).interpretation(Clarification)

    def extract(self, definition):
        parser_term = Parser(self.create_term_rule())
        parser_volume = Parser(self.create_volume_rule())
        parser_clar_left = Parser(self.create_clarification_rule(is_left=True))
        parser_clar_right = Parser(self.create_clarification_rule(is_left=False))


        definition = definition.replace('−', '-')
        sentence = definition

        fact_d = {}

        match = parser_term.find(sentence)
        if match:
            fact_d['термин'] = match.fact.name

        match = parser_volume.find(sentence)
        if match:
            fact_d['Объем'] = (match.fact.sign, match.fact.volume)

        fact_d['Уточнение объема'] = {}

        match = parser_clar_left.find(sentence)
        if match:
            fact_d['Уточнение объема']['Левая часть уточнения'] = (
                match.fact.pre_first_relation,
                match.fact.first_relation,
                match.fact.term_1
            )

        match = parser_clar_right.find(sentence)
        if match:
            fact_d['Уточнение объема']['Правая часть уточнения'] = (
                match.fact.pre_second_relation,
                match.fact.second_relation,
                match.fact.term_2
            )

        return fact_d
    
    def db_row_to_fact_d(self, row: tuple, column_names: list[str]) -> dict:
        d = dict(zip(column_names, row))
        d.pop('id', None)
        d.pop('domain_id', None)

        # Парсим кортеж Объема из строки, если он хранится строкой
        volume = d.get('volume')
        if isinstance(volume, str):
            try:
                volume = ast.literal_eval(volume)
            except Exception:
                volume = None

        # Аналогично для уточнений, если там строки с кортежами
        def parse_tuple_field(field_name):

            val = d.get(field_name)

            if isinstance(val, str):
                try:
                    return ast.literal_eval(val)
                except Exception:
                    return (None, None, None)
            return val or (None, None, None)

        clar_left = parse_tuple_field('left_clar')
        clar_right = parse_tuple_field('right_clar')

        if clar_left == ('', '', '') and clar_right == ('', '', ''):
            return {
                'термин': d.get('term'),
                'Объем': volume,
                'Уточнение объема': {}
            }
        elif clar_right == ('', '', ''):
            return {
                'термин': d.get('term'),
                'Объем': volume,
                'Уточнение объема': {
                    'Левая часть уточнения': clar_left
                }
            }
        else:
            return {
                'термин': d.get('term'),
                'Объем': volume,
                'Уточнение объема': {
                    'Левая часть уточнения': clar_left,
                    'Правая часть уточнения': clar_right,
                }
            }
    
    def reconstruct(self, fact_d: dict) -> str:
        parts = ''
        term_key = next((k for k in fact_d if k.startswith("термин")), None)
        if term_key:
            term = fact_d[term_key]
            parts += f"Объем понятия {term} "

        if 'Объем' in fact_d:
            sign, volume = fact_d['Объем']
            if sign:
                parts += f"состоит из {sign} {volume} значений"
            else:
                parts += f"состоит из {volume} значений"

        clar = fact_d.get('Уточнение объема', {})
        if 'Левая часть уточнения' in clar:
            pre, rel, term = clar['Левая часть уточнения']
            parts += f", элементы которого {pre + ' ' if pre else ''}{rel if pre else rel + ' либо равны'} {term}"

        if 'Правая часть уточнения' in clar:
            pre, rel, term = clar['Правая часть уточнения']
            parts += f", но {pre + ' ' if pre else ''}{rel if pre else rel + ' либо равны'} {term}"

        return parts
# --- Скалярные величины ---
class ScalarExtractor(BaseExtractorStrategy):
    def extract(self, definition):
        # Пример: "Объем понятия термин состоит из множества скалярных значений: {значение_1, значение_2, ..., значение_n}"
        Term = fact('Term', ['name'])
        ScalarVolume = fact('ScalarVolume', ['values', 'volume'])

        term_rule = rule(
            eq('Объем'),
            eq('понятия'),
            rule(
                gram('ADJF').optional().repeatable(),
                gram('NOUN').repeatable()
            ).interpretation(Term.name)
        ).interpretation(Term)

        scalar_volume_rule = rule(
            eq('состоит'),
            eq('из'),
            eq('множества'),
            eq('скалярных').interpretation(ScalarVolume.volume),
            eq('значений'),
            eq(':'),
            or_(
                rule(
                    rule(
                        gram('ADJF').optional().repeatable(),
                        gram('NOUN').repeatable(), eq(',')
                        ).repeatable(),
                    gram('ADJF').optional().repeatable(),
                    gram('NOUN').repeatable()
                ),
                rule(
                    gram('ADJF').optional().repeatable(),
                    gram('NOUN').repeatable()
                )
            ).interpretation(ScalarVolume.values)
        ).interpretation(ScalarVolume)

        parser_term = Parser(term_rule)
        parser_scalar = Parser(scalar_volume_rule)

        sentence = definition

        fact_d = {}

        m_term = parser_term.find(sentence)
        if m_term:
            fact_d['термин'] = m_term.fact.name

        m_scalar = parser_scalar.find(sentence)
        if m_scalar:
            fact_d['Объем'] = m_scalar.fact.volume
            if ',' in m_scalar.fact.values:
                m_scalar_list = m_scalar.fact.values.split(',')
                fact_d['Уточнение объема'] = m_scalar_list
            else:
                m_scalar_list = [m_scalar.fact.values]
                fact_d['Уточнение объема'] = m_scalar_list

        return fact_d
    
    def db_row_to_fact_d(self, row: tuple, column_names: list[str]) -> dict:
        d = dict(zip(column_names, row))
        # Убираем лишние поля
        d.pop('id', None)
        d.pop('domain_id', None)
        # Преобразуем обратно в оригинальную структуру
        return {
            'термин': d['term'],
            'Объем': d['volume'],
            'Уточнение объема': [s.strip() for s in d['values_list'].split(',')] if d['values_list'] else []
        }

    def reconstruct(self, fact_d: dict) -> str:
        parts = ''
        term_key = next((k for k in fact_d if k.startswith("термин")), None)
        if term_key:
            term = fact_d[term_key]
            parts += f"Объем понятия {term} "

        if 'Объем' in fact_d:
            volume = fact_d['Объем']
            values = fact_d.get('Уточнение объема', [])
            values_str = ', '.join(values)
            parts += f"состоит из множества {volume} значений: {values_str}"

        return parts

# --- Величины множеств ---
class SetExtractor(BaseExtractorStrategy):
    def extract(self, definition):
        import re
        from yargy.interpretation import fact
        from yargy import rule, or_
        from yargy.predicates import eq, gram
        from yargy import Parser

        Term = fact('Term', ['name'])
        SetVolume = fact('SetVolume', ['subset_type', 'set1', 'operation', 'set2'])

        # --------------------------
        # Извлечение термина: "Объем понятия ... состоит из"
        # --------------------------
        def extract_term_name(text):
            pattern = r'Объем понятия\s+(.*?)\s+состоит из'
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
            return None

        # множество_1 и множество_2
        noun_phrase = rule(gram('ADJF').optional(), gram('NOUN').repeatable())

        # базовый случай: подмножеств множества N
        base_rule = rule(
            eq('подмножеств'),
            eq('множества'),
            noun_phrase.interpretation(SetVolume.set1)
        )

        # исключение: за исключением подмножеств, которым принадлежат элементы множества N
        exception_rule = rule(
            eq('за'),
            eq('исключением'),
            eq('подмножеств'),
            eq(','),
            eq('которым'),
            eq('принадлежат'),
            eq('элементы'),
            eq('множества'),
            noun_phrase.interpretation(SetVolume.set2)
        )

        # пересечение: подмножеств пересечения множеств A и B
        intersection_rule = rule(
            eq('подмножеств'),
            eq('пересечения'),
            eq('множеств'),
            noun_phrase.interpretation(SetVolume.set1),
            eq('и'),
            noun_phrase.interpretation(SetVolume.set2)
        )

        # объединение: подмножеств объединения множеств A и B
        union_rule = rule(
            eq('подмножеств'),
            eq('объединения'),
            eq('множеств'),
            noun_phrase.interpretation(SetVolume.set1),
            eq('и'),
            noun_phrase.interpretation(SetVolume.set2)
        )

        # полный объемный шаблон
        prefix_rule = rule(
            eq('состоит'),
            eq('из'),
            eq('конечных'),
            eq('непустых').optional().interpretation(SetVolume.subset_type)
        )

        full_rule = rule(
            prefix_rule,
            or_(
                rule(base_rule, exception_rule),
                intersection_rule,
                union_rule,
                base_rule
            )
        ).interpretation(SetVolume)

        parser_volume = Parser(full_rule)

        sentence = definition
        fact_d = {}

        # Термин (через шаблон)
        term_name = extract_term_name(sentence)
        if term_name:
            fact_d['термин'] = term_name

        # Объем
        m_vol = parser_volume.find(sentence)
        if m_vol:
            vol = m_vol.fact

            operation = None
            set1 = getattr(vol, 'set1', None)
            set2 = getattr(vol, 'set2', None)
            subset_type = getattr(vol, 'subset_type', None)

            if 'пересечения' in sentence:
                operation = 'пересечение'
            elif 'объединения' in sentence:
                operation = 'объединение'
            elif 'за исключением' in sentence:
                operation = 'исключение'

            fact_d['Объем'] = (subset_type, 'множеств') 
            fact_d['Уточнение объема'] = {
                'множество_1': set1 if set1 else None,
                'операция': operation,
                'множество_2': set2 if set2 else None
            }

        return fact_d
    
    def db_row_to_fact_d(self, row: tuple, column_names: list[str]) -> dict:
        d = dict(zip(column_names, row))
        d.pop('id', None)
        d.pop('domain_id', None)
        return {
            'термин': d['term'],
            'Объем': (d['subset_type'], 'множеств'),
            'Уточнение объема': {
                'множество_1': d['set1'],
                'операция': d['operation'],
                'множество_2': d['set2']
            }
        }
    
    def reconstruct(self, fact_d: dict) -> str:
        parts = ''
        term_key = next((k for k in fact_d if k.startswith("термин")), None)
        if term_key:
            term = fact_d[term_key]
            parts += f"Объем понятия {term} "

        if 'Объем' in fact_d:
            subset_type, _ = fact_d['Объем']
            clarification = fact_d.get('Уточнение объема', {})
            set1 = clarification.get('множество_1')
            set2 = clarification.get('множество_2')
            op = clarification.get('операция')

            start = "состоит из конечных"
            if subset_type:
                start += f" {subset_type}"
            start += " подмножеств"

            if op == "объединение" and set1 and set2:
                parts += f"{start} объединения множеств {set1} и {set2}"
            elif op == "пересечение" and set1 and set2:
                parts += f"{start} пересечения множеств {set1} и {set2}"
            elif op == "исключение" and set2:
                parts += f"{start} множества {set1} за исключением подмножеств, которым принадлежат элементы множества {set2}"
            elif set1:
                parts += f"{start} множества {set1}"
            else:
                parts += start

        return parts

# --- Величины отображений ---
class MappingExtractor(BaseExtractorStrategy):
    def extract(self, definition):

        Term = fact('Term', ['name'])
        MappingVolume = fact('MappingVolume', ['volume'])
        Domain = fact('Domain', ['definition_domain'])
        Codomain = fact('Codomain', ['value_domain'])

        # --- Правила ---
        term_rule = rule(
            eq('Объем'),
            eq('понятия'),
            rule(
                gram('ADJF').optional().repeatable(),
                gram('NOUN').repeatable()
            ).interpretation(Term.name)
        ).interpretation(Term)

        volume_rule = rule(
            eq('состоит'),
            eq('из'),
            eq('конечных'),
            eq('отображений').interpretation(MappingVolume.volume)
        ).interpretation(MappingVolume)

        domain_rule = rule(
            eq('Областью'),
            eq('определения'),
            eq('отображения'),
            eq('является'),
            rule(
                gram('NOUN').optional(),
                gram('ADJF').optional().repeatable(),
                gram('NOUN').repeatable()
            ).interpretation(Domain.definition_domain)  
        ).interpretation(Domain)

        codomain_rule = rule(
            eq('Областью'),
            eq('значений'),
            eq('отображения'),
            eq('является'),
            rule(
                gram('NOUN').optional(),
                gram('ADJF').optional().repeatable(),
                gram('NOUN').repeatable()
            ).interpretation(Codomain.value_domain)
        ).interpretation(Codomain)

        # --- Парсеры ---
        parser_term = Parser(term_rule)
        parser_volume = Parser(volume_rule)
        parser_domain = Parser(domain_rule)
        parser_codomain = Parser(codomain_rule)

        fact_d = {}

        m_term = parser_term.find(definition)
        if m_term:
            fact_d['термин'] = m_term.fact.name

        m_vol = parser_volume.find(definition)
        if m_vol:
            fact_d['Объем'] = m_vol.fact.volume

        fact_d['Уточнение объема'] = {}

        m_def = parser_domain.find(definition)
        if m_def:
            fact_d['Уточнение объема']['Область определения'] = m_def.fact.definition_domain

        m_cod = parser_codomain.find(definition)
        if m_cod:
            fact_d['Уточнение объема']['Область значений'] = m_cod.fact.value_domain

        return fact_d

    def reconstruct(self, fact_d: dict) -> str:
        parts = ''
        term_key = next((k for k in fact_d if k.startswith("термин")), None)
        if term_key:
            term = fact_d[term_key]
            parts += f"Объем понятия {term} состоит из конечных отображений."

        clar = fact_d.get('Уточнение объема', {})
        if 'Область определения' in clar:
            parts += f" Областью определения отображения является {clar['Область определения']}."
        if 'Область значений' in clar:
            parts += f" Областью значений отображения является {clar['Область значений']}."

        return parts

    def db_row_to_fact_d(self, row: tuple, column_names: list[str]) -> dict:
        row_d = dict(zip(column_names, row))
        return {
            'термин': row_d.get('term', ''),
            'Объем': row_d.get('volume', ''),
            'Уточнение объема': {
                'Область определения': row_d.get('domain', ''),
                'Область значений': row_d.get('codomain', '')
            }
        }

# --- Объединённые величины ---
class UnionExtractor(BaseExtractorStrategy):
    def extract(self, text: str) -> dict:
        """
        Извлекает факт из определения вида:
        Объем понятия Протокол состоит из значений, принадлежащих объединению множеств объемов понятий,
        обозначенных терминами HTTP, FTP, SMTP
        """
        pattern = re.compile(
            r'Объем понятия (?P<term>[\w\s\-]+) состоит из значений, принадлежащих объединению множеств объемов понятий, '
            r'обозначенных терминами (?P<terms>[\w\d\s,]+)',
            re.IGNORECASE
        )
        match = pattern.search(text)
        if not match:
            return {}

        main_term = match.group('term').strip()
        subterms_raw = match.group('terms')
        subterms = [t.strip() for t in subterms_raw.split(',') if t.strip()]

        return {
            'термин': main_term,
            'Объем': 'объединенные величины',
            'Уточнение объема': subterms
        }

    def db_row_to_fact_d(self, row: tuple, column_names: list[str]) -> dict:
        # Преобразуем к dict для удобства
        row_dict = dict(zip(column_names, row))

        term = row_dict.get('term', '')
        volume = row_dict.get('volume', '')
        union_terms_str = row_dict.get('union_terms_list', '')
        union_terms = [term.strip() for term in union_terms_str.split(',')] if union_terms_str else []

        fact_d = {
            'термин': term,
            'Объем': volume,
            'Уточнение объема': union_terms
        }
        return fact_d

    def reconstruct(self, fact_d: dict) -> str:
        term = fact_d.get('термин', '')
        subterms = fact_d.get('Уточнение объема', [])
        subterms_str = ', '.join(subterms)

        return (
            f'Объем понятия {term} состоит из значений, принадлежащих объединению множеств объемов понятий, '
            f'обозначенных терминами {subterms_str}.'
        )

# --- Структурные величины ---
class StructuralExtractor(BaseExtractorStrategy):
    # Паттерн и логика извлечения
    def extract(self, definition: str) -> dict:
        pattern = (
            r"Объем понятия\s+(?P<term>.+?)\s+состоит из конечных подмножеств структурных объектов, "
            r"имеющих одну и ту же структуру\. Атрибутами этих структурных объектов являются\s+(?P<attrs>.+)$"
        )
        match = re.match(pattern, definition.strip())
        if not match:
            return {}

        term = match.group('term').strip()
        attrs_raw = match.group('attrs').strip()

        # Разбиваем атрибуты по запятой и убираем лишние пробелы
        attrs = [attr.strip() for attr in attrs_raw.split(',') if attr.strip()]

        return {
            'термин': term,
            'Объем': 'структурные величины',
            'Уточнение объема': attrs
        }
    
    def db_row_to_fact_d(self, row: tuple, column_names: list[str]) -> dict:
        row_dict = dict(zip(column_names, row))
        term = row_dict.get('term', '')
        volume = row_dict.get('volume', '')
        attrs_str = row_dict.get('attrs_list', '')
        attrs = [a.strip() for a in attrs_str.split(',')] if attrs_str else []

        fact_d = {
            'термин': term,
            'Объем': volume,
            'Уточнение объема': attrs
        }
        return fact_d
    
    def reconstruct(self, fact_d: dict) -> str:
        term = fact_d.get('термин', '')
        attrs = fact_d.get('Уточнение объема', [])
        attrs_str = ', '.join(attrs)
        return (f"Объем понятия {term} состоит из конечных подмножеств структурных объектов, "
                f"имеющих одну и ту же структуру. Атрибутами этих структурных объектов являются {attrs_str}")

# --- Величины последовательностей ---
class SequenceExtractor(BaseExtractorStrategy):
    def extract(self, definition: str) -> dict:
        pattern = (
            r"Объем понятия\s+(?P<term>.+?)\s+состоит из бесконечного множества конечных последовательностей, "
            r"элементы каждой последовательности принадлежат конечному множеству\s+(?P<set_name>.+)$"
        )
        
        match = re.match(pattern, definition.strip())
        if not match:
            return {}
        
        term = match.group('term').strip()
        set_name = match.group('set_name').strip()
        
        return {
            'термин': term,
            'Объем': 'величины последовательностей',
            'Уточнение объема': set_name
        }
    
    def db_row_to_fact_d(self, row: tuple, column_names: list[str]) -> dict:

        data = dict(zip(column_names, row))
        return {
            'термин': data.get('term', ''),
            'Объем': data.get('volume', ''),
            'Уточнение объема': data.get('clarification', '')
        }

    def reconstruct(self, fact_d: dict) -> str:
        term = fact_d.get('термин', '')
        volume = fact_d.get('Объем', '')
        clarification = fact_d.get('Уточнение объема', '')

        # Формируем текст строго по шаблону
        return (f"Объем понятия {term} состоит из бесконечного множества конечных последовательностей, "
                f"элементы каждой последовательности принадлежат конечному множеству {clarification}")

# Основной класс с паттерном Стратегия
class TermExtractor:

    def __init__(self, strategy: BaseExtractorStrategy, db_path='terms.db'):
        self.strategy = strategy
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_domains_table()
        self.table_map = {
            'DimensionalExtractor': ('dimensional_terms', ['term', 'volume', 'left_clar', 'right_clar']),
            'ScalarExtractor': ('scalar_terms', ['term', 'volume', 'values_list']),
            'SetExtractor': ('set_terms', ['term', 'subset_type', 'set1', 'operation', 'set2']),
            'MappingExtractor': ('mapping_terms', ['term', 'volume', 'domain', 'codomain']),
            'UnionExtractor': ('union_terms', ['term', 'volume', 'union_terms_list']),
            'StructuralExtractor': ('structural_terms', ['term', 'volume', 'attrs_list']),
            'SequenceExtractor': ('sequence_terms', ['term', 'volume', 'clarification'])
        }
        
        self.strategy_classes = {
            'DimensionalExtractor': DimensionalExtractor,
            'ScalarExtractor': ScalarExtractor,
            'SetExtractor': SetExtractor, 
            'MappingExtractor': MappingExtractor,
            'UnionExtractor': UnionExtractor,
            'StructuralExtractor': StructuralExtractor,
            'SequenceExtractor': SequenceExtractor
        }

    def set_strategy(self, strategy: BaseExtractorStrategy):
        self.strategy = strategy

    def extract_terms(self, definition):
        return self.strategy.extract(definition)
    
    def reconstruct_terms_str(self, fact_d):
        return self.strategy.reconstruct(fact_d)

    def _create_domains_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_order (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER,
                table_name TEXT,
                term_id INTEGER,
                order_index INTEGER,
                FOREIGN KEY(domain_id) REFERENCES domains(id) ON DELETE CASCADE,
                UNIQUE(domain_id, order_index)
            )
        ''')
        self.conn.commit()

    def _get_or_create_domain_id(self, domain_name):
        self.cursor.execute('SELECT id FROM domains WHERE name = ?', (domain_name,))
        row = self.cursor.fetchone()
        if row:
            return row[0]
        self.cursor.execute('INSERT INTO domains (name) VALUES (?)', (domain_name,))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_all_terms_for_domain(self, domain_id):
        """Возвращает список кортежей (table_name, term) для всех терминов в указанной предметной области."""
        terms = []
        for strategy_name in self.table_map:
            table_name, fields = self.table_map[strategy_name]
            self._create_term_table_if_not_exists(table_name, fields)
            self.cursor.execute(f'SELECT term FROM {table_name} WHERE domain_id = ?', (domain_id,))
            rows = self.cursor.fetchall()
            for row in rows:
                terms.append((table_name, row[0]))
        return terms

    def delete_term(self, domain_id, table_name, term):
        """Удаляет термин из указанной таблицы и соответствующую запись в global_order."""
        # Получение term_id
        self.cursor.execute(f'SELECT id FROM {table_name} WHERE domain_id = ? AND term = ?', (domain_id, term))
        row = self.cursor.fetchone()
        if not row:
            return
        term_id = row[0]

        # Удаление из таблицы терминов
        self.cursor.execute(f'DELETE FROM {table_name} WHERE id = ?', (term_id,))

        # Удаление из global_order
        self.cursor.execute('''
            DELETE FROM global_order 
            WHERE domain_id = ? AND table_name = ? AND term_id = ?
        ''', (domain_id, table_name, term_id))
        self.conn.commit()

    def _create_term_table_if_not_exists(self, table_name, fields):
        field_defs = ', '.join([f'{field} TEXT' for field in fields])
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER,
                {field_defs},
                FOREIGN KEY(domain_id) REFERENCES domains(id) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

    def save_to_db(self, fact_d, domain_name):
        domain_id = self._get_or_create_domain_id(domain_name)

        strategy_class_name = self.strategy.__class__.__name__
        if strategy_class_name not in self.table_map:
            raise ValueError(f"Strategy '{strategy_class_name}' не зарегистрирован в table_map")

        table_name, fields = self.table_map[strategy_class_name]
        self._create_term_table_if_not_exists(table_name, fields)

        term = fact_d.get('термин', '').strip()
        if not term:
            return  # Пропуск, если термин пустой

        # Проверка существования термина в базе
        self.cursor.execute(f'''
            SELECT id, {', '.join(fields)} 
            FROM {table_name} 
            WHERE domain_id = ? AND term = ?
        ''', (domain_id, term))
        existing_row = self.cursor.fetchone()

        # Формирование значений для вставки/обновления
        values = []
        if strategy_class_name == 'DimensionalExtractor':
            term = fact_d.get('термин', '')
            volume = fact_d.get('Объем', (None, None))
            left = fact_d.get('Уточнение объема', {}).get('Левая часть уточнения', ('', '', ''))
            right = fact_d.get('Уточнение объема', {}).get('Правая часть уточнения', ('', '', ''))
            values = [term, str(volume), str(left), str(right)]
        elif strategy_class_name == 'ScalarExtractor':
            term = fact_d.get('термин', '')
            volume = fact_d.get('Объем', '')
            values_list = fact_d.get('Уточнение объема', [])
            values = [term, volume, ', '.join(values_list)]
        elif strategy_class_name == 'SetExtractor':
            term = fact_d.get('термин', '')
            subset_type, _ = fact_d.get('Объем', ('', ''))
            clar = fact_d.get('Уточнение объема', {})
            values = [term, subset_type, clar.get('множество_1', ''), clar.get('операция', ''), clar.get('множество_2', '')]
        elif strategy_class_name == 'MappingExtractor':
            term = fact_d.get('термин', '')
            volume = fact_d.get('Объем', '')
            clar = fact_d.get('Уточнение объема', {})
            domain = clar.get('Область определения', '')
            codomain = clar.get('Область значений', '')
            values = [term, volume, domain, codomain]
        elif strategy_class_name == 'UnionExtractor':
            term = fact_d.get('термин', '')
            volume = fact_d.get('Объем', '')
            union_terms = fact_d.get('Уточнение объема', [])
            values = [term, volume, ', '.join(union_terms)]
        elif strategy_class_name == 'StructuralExtractor':
            term = fact_d.get('термин', '')
            volume = fact_d.get('Объем', '')
            attrs = fact_d.get('Уточнение объема', [])
            values = [term, volume, ', '.join(attrs)]
        elif strategy_class_name == 'SequenceExtractor':
            term = fact_d.get('термин', '')
            volume = fact_d.get('Объем', '')
            clarification = fact_d.get('Уточнение объема', '')
            values = [term, volume, clarification]

        if existing_row:
            existing_values = list(existing_row[1:])  # Пропуск id
            if values == existing_values:
                return  # Нет изменений
            else:
                # Обновление записи
                set_clause = ', '.join([f'{field}=?' for field in fields])
                self.cursor.execute(f'''
                    UPDATE {table_name} 
                    SET {set_clause} 
                    WHERE id = ?
                ''', values + [existing_row[0]])
        else:
            # Вставка новой записи
            placeholders = ', '.join('?' for _ in fields)
            self.cursor.execute(
                f'''INSERT INTO {table_name} (domain_id, {', '.join(fields)}) 
                VALUES (?, {placeholders})''',
                [domain_id] + values
            )
            term_id = self.cursor.lastrowid

            # Обновление global_order
            self.cursor.execute('''
                SELECT MAX(order_index) FROM global_order WHERE domain_id = ?
            ''', (domain_id,))
            max_order = self.cursor.fetchone()[0] or 0
            new_order = max_order + 1

            self.cursor.execute('''
                INSERT INTO global_order 
                (domain_id, table_name, term_id, order_index)
                VALUES (?, ?, ?, ?)
            ''', (domain_id, table_name, term_id, new_order))

        self.conn.commit()

    def get_term_data(self, table_name: str, term_id: int) -> dict:
        self.cursor.execute(f'SELECT * FROM {table_name} WHERE id = ?', (term_id,))
        row = self.cursor.fetchone()
        column_names = [desc[0] for desc in self.cursor.description]
        return dict(zip(column_names, row)) if row else {}

    def load_from_db(
        self, 
        table_name: str, 
        domain_name: str, 
        strategy: BaseExtractorStrategy, 
        use_global_order: bool = False
    ) -> list[dict]:
        domain_id = self._get_domain_id(domain_name)
        if domain_id is None:
            return []

        if use_global_order:
            # Загрузка терминов в порядке из global_order
            self.cursor.execute('''
                SELECT table_name, term_id 
                FROM global_order 
                WHERE domain_id = ? 
                ORDER BY order_index
            ''', (domain_id,))
            ordered_entries = self.cursor.fetchall()
            terms = []
            for tbl_name, term_id in ordered_entries:
                query = f'SELECT * FROM {tbl_name} WHERE id = ? AND domain_id = ?'
                self.cursor.execute(query, (term_id, domain_id))
                row = self.cursor.fetchone()
                if not row:
                    continue
                column_names = [desc[0] for desc in self.cursor.description]
                # Определение стратегии по имени таблицы
                strategy_class_name = next(
                    (k for k, v in self.table_map.items() if v[0] == tbl_name),
                    None
                )
                if not strategy_class_name:
                    continue
                strategy_class = self.strategy_classes.get(strategy_class_name)
                if not strategy_class:
                    continue
                strategy_instance = strategy_class()
                terms.append(strategy_instance.db_row_to_fact_d(row, column_names))
            return terms
        else:
            # Стандартная загрузка из указанной таблицы
            query = f'SELECT * FROM {table_name} WHERE domain_id = ?'
            self.cursor.execute(query, (domain_id,))
            rows = self.cursor.fetchall()
            column_names = [desc[0] for desc in self.cursor.description]
            return [strategy.db_row_to_fact_d(row, column_names) for row in rows]
        
    def get_ordered_terms(self, domain_name: str) -> list[tuple]:
        domain_id = self._get_domain_id(domain_name)
        if not domain_id:
            return []

        self.cursor.execute('''
            SELECT table_name, term_id 
            FROM global_order 
            WHERE domain_id = ? 
            ORDER BY order_index
        ''', (domain_id,))
        return self.cursor.fetchall()
    
    def get_template_type(self, table_name: str) -> str:
        for key, value in self.table_map.items():
            if value[0] == table_name:
                return key.replace("Extractor", "").lower()
        return ""
    
    def _get_domain_id(self, domain_name: str) -> int | None:
        self.cursor.execute('SELECT id FROM domains WHERE name = ?', (domain_name,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    