import os
import json
import re
from term_extractor import TermExtractor, ScalarExtractor, DimensionalExtractor, SetExtractor, MappingExtractor, UnionExtractor, StructuralExtractor, SequenceExtractor

class ModelGenerator:
    def __init__(self, selected_subject):
        self.selected_subject = selected_subject
        self.extractor = TermExtractor(strategy=None)
        
    def build_concepts_model(self):
        
        line_list = []
        terms = self.extractor.load_from_db('scalar_terms', self.selected_subject, None, True)
        for term in terms:
            if term['Объем'] == 'скалярных':
                self.extractor.set_strategy(ScalarExtractor())
                line = self.extractor.reconstruct_terms_str(term)
                
                line = line.replace('Объем понятия', 'Сорт')
                line = line.replace(' состоит из', ':')
                line = line.replace('множества скалярных значений: ', '{')
                line = line.replace('  ', ' ')
                line = line+'}'
                # print(line)
            elif 'размерных' in term['Объем']:
                self.extractor.set_strategy(DimensionalExtractor())
                line = self.extractor.reconstruct_terms_str(term)
                line = line.replace('Объем понятия', 'Сорт')
                line = line.replace(' состоит из', ':')
                line = line.replace(' неположительных размерных значений', ' R(-∞, 0]')
                line = line.replace(' отрицательных размерных значений', ' R(-∞, 0)')
                line = line.replace(' неотрицательных размерных значений', ' R[0, ∞)')
                line = line.replace(' положительных размерных значений', ' R(0, ∞)')
                line = line.replace(' размерных значений, элементы которого больше либо равны -∞', ' R(-∞')
                line = line.replace(' размерных значений, элементы которого строго больше ,', ' R')
                line = line.replace(' размерных значений, элементы которого больше либо равны ', ' R[')
                line = line.replace(' размерных значений, элементы которого строго больше ', ' R(')
                if ', но меньше либо равны ∞' in line:
                    line += ')'
                    line = line.replace(', но меньше либо равны', ',')
                elif ', но меньше либо равны' in line:
                    line += ']'
                    line = line.replace(', но меньше либо равны', ',')
                elif ', но строго меньше' in line:
                    line += ')'
                    line = line.replace(', но строго меньше', ',')
                # print(line)
            elif 'множеств' in term['Объем']:
                self.extractor.set_strategy(SetExtractor())
                line = self.extractor.reconstruct_terms_str(term)
                line = line.replace('Объем понятия', 'Сорт')
                line = line.replace(' состоит из', ':')
                if " непустых " in line:
                    line = line.replace(' конечных непустых подмножеств ', " {}")
                    line += " непустых "
                line = line.replace(' конечных подмножеств ', " {}")
                line = line.replace('множества названий', 'N')
                line = line.replace('множества вещественных чисел', 'R')
                line = line.replace('множества целых чисел', 'I')
                if ' за исключением подмножеств, которым принадлежат' in line:
                    line = line.replace('{}множества ', '{}(')
                    line = line.replace(' за исключением подмножеств, которым принадлежат элементы множества ', ' \ ')
                    line += ')'
                    if ' непустых ' in line:
                        line = line.replace(' непустых ', '')+' \ Ø'
                if 'пересечения множеств ' in line:
                    line = line.replace('пересечения множеств ', '(')
                    line = line.replace(' и ', ' ⋃ ')
                    line += ')'
                    if ' непустых ' in line:
                        line = line.replace(' непустых ', '')+' \ Ø'
                if 'объединения множеств ' in line:
                    line = line.replace('объединения множеств ', '(')
                    line = line.replace(' и ', ' ⋂ ')
                    line += ')'
                    if ' непустых ' in line:
                        line = line.replace(' непустых ', '')+' \ Ø'
                if ' непустых ' in line:
                    line = line.replace(' непустых ', '')+' \ Ø'
                if '{}множества ' in line:
                    line = line.replace('{}множества ', '{}')
                # print(line)
            elif term['Объем'] == 'отображений':
                self.extractor.set_strategy(MappingExtractor())
                line = self.extractor.reconstruct_terms_str(term)
                line = line.replace('Объем понятия', 'Сорт')
                line = line.replace(' состоит из', ':')
                line = line.replace(" конечных отображений. Областью определения отображения является ", " (")
                line = line.replace(". Областью значений отображения является ", " → ")
                line = line.replace(".", ")")
                line = line.replace('множество названий', 'N')
                line = line.replace('множество вещественных чисел', 'R')
                line = line.replace('множество целых чисел', 'I')
                # print(line)
            elif term['Объем'] == 'объединенные величины':
                self.extractor.set_strategy(UnionExtractor())
                line = self.extractor.reconstruct_terms_str(term)
                line = line.replace('Объем понятия', 'Сорт')
                line = line.replace(' состоит из', ':')
                line = line.replace("значений, принадлежащих объединению множеств объемов понятий, обозначенных терминами ", "")
                line = line.replace(", ", " ∪ ")
                line = line.replace('.', '')
                # print(line)
            elif term['Объем'] == 'структурные величины':
                self.extractor.set_strategy(StructuralExtractor())
                line = self.extractor.reconstruct_terms_str(term)
                line = line.replace('Объем понятия', 'Сорт')
                line = line.replace(' состоит из', ':')
                line = line.replace("конечных подмножеств структурных объектов, имеющих одну и ту же структуру. Атрибутами этих структурных объектов являются ", "{}N")
                for i in term['Уточнение объема']:
                    line = line.replace(i, '')
                    line = line.replace(',', '')
            elif term['Объем'] == 'величины последовательностей':
                self.extractor.set_strategy(SequenceExtractor())
                line = self.extractor.reconstruct_terms_str(term)
                line = line.replace('Объем понятия', 'Сорт')
                line = line.replace(' состоит из', ':')
                line = line.replace("бесконечного множества конечных последовательностей, элементы каждой последовательности принадлежат конечному множеству ", "seq ")
                line = line.replace(".", "")
                # print(line)

            line_list.append(line)

        filename = f'{self.selected_subject}_model.json'
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as file:
                data = json.load(file)
        else:
            data = {"понятия": [], "онтологические соглашения": [], "знания": []} 

        data["понятия"] = line_list

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def build_formula_model(self):
        
        try:
            with open(f"{self.selected_subject}_ontology_list_terms.json", encoding="utf-8") as f:
                terms_list = json.load(f)  # список строк терминов, например: ["отображение шаров", "радиус", ...]
        except:
            terms_list = []
        try:
            with open(f"{self.selected_subject}_knowledge_list_terms.json", encoding="utf-8") as f:
                knowledge_terms_list = json.load(f)
        except:
            knowledge_terms_list = []

        terms_list += knowledge_terms_list
        terms_list = sorted(terms_list, key=len, reverse=True)

        def natural_to_formal(natural_expr, formula_type, tree_output_path="expression_tree.json"):
            var_counter = [1]  # счётчик для переменных v1, v2, ...

            # === Обработка кванторов "для значения понятия ..." (рекурсивная) ===
            def process_universal_quantifiers(expr):
                pattern = r"для\s+(?:любого\s+)?значения\s+понятия\s+([А-Яа-яA-Za-zA-Z0-9_]+(?:\s+[А-Яа-яA-Za-zA-Z0-9_]+)*)"
                match = re.search(pattern, expr)
                if not match:
                    return expr

                start, end = match.span()
                concept = match.group(1).strip()
                var_name = f"v{var_counter[0]}"
                var_counter[0] += 1

                before = expr[:start]
                after_text_raw = expr[end:].lstrip(" ,")

                # 2. Найдём самый длинный термин из terms_list, который является префиксом after_text_raw
                matched_term = None
                for term in terms_list:
                    if after_text_raw.startswith(term):
                        matched_term = term
                        break

                if matched_term:
                    # Вставляем (vN) после matched_term
                    after_processed_inner = f"{matched_term}({var_name})" + after_text_raw[len(matched_term):]
                else:
                    # Если не нашли — fallback к первому слову
                    m = re.match(r"(\w+)(.*)", after_text_raw, re.DOTALL)
                    if m:
                        first_word, rest = m.groups()
                        after_processed_inner = f"{first_word}({var_name}){rest}"
                    else:
                        after_processed_inner = after_text_raw

                # Рекурсивно обрабатываем остаток
                after_processed = process_universal_quantifiers(after_processed_inner)

                return before + f"({var_name}: {concept})" + after_processed

            # === Обработка операций над множествами ===
            def process_set_operations(expr):
                expr = re.sub(r"\(пересечение\s+([^)]+?)\s+и\s+([^)]+?)\)", r"(\1 ∩ \2)", expr)
                expr = re.sub(r"\(объединение\s+([^)]+?)\s+и\s+([^)]+?)\)", r"(\1 ∪ \2)", expr)
                expr = re.sub(r"\(разность\s+([^)]+?)\s+и\s+([^)]+?)\)", r"(\1 ∖ \2)", expr)
                return expr

            # === Обработка операций над размерными величинами ===
            def process_dimensional_operations(expr):
                expr = re.sub(r"\(возведение\s+([^)]+?)\s+в\s+степень\s+([^)]+?)\)", r"(\1↑\2)", expr)
                expr = re.sub(r"\(деление\s+([^)]+?)\s+на\s+([^)]+?)\)", r"(\1 / \2)", expr)
                expr = re.sub(r"\(произведение\s+([^)]+?)\s+и\s+([^)]+?)\)", r"(\1 ⋅ \2)", expr)
                expr = re.sub(r"\(сумма\s+([^)]+?)\s+и\s+([^)]+?)\)", r"(\1 + \2)", expr)
                return expr

            replacements = {
                "не является подмножеством": "⊄",
                "является подмножеством либо равно": "⊆",
                "является подмножеством": "⊂",
                "не принадлежит": "∉",
                "принадлежит": "∈",
                "не равен": "≠",
                "не равно": "≠",
                "больше либо равен": "≥",
                "меньше либо равен": "≤",
                "строго больше": ">",
                "строго меньше": "<",
                "больше": ">",
                "меньше": "<",
                "равен": "=",
                "равно": "=",
            }

            logical_replacements = {
                " тогда и только тогда, когда ": " ⇔ ",
                " если ": "",
                " то ": " ⇒ ",
                " и ": " ∧ ",
                " или ": " ∨ ",
            }

            # === Шаги 1-6: Преобразование текста ===
            
            natural_expr = process_set_operations(natural_expr)
            natural_expr = process_dimensional_operations(natural_expr)
            natural_expr = process_universal_quantifiers(natural_expr)  # <--- новая обработка

            for nat, formal in sorted(replacements.items(), key=lambda x: -len(x[0])):
                natural_expr = natural_expr.replace(nat, formal)

            for nat, formal in sorted(logical_replacements.items(), key=lambda x: -len(x[0])):
                natural_expr = natural_expr.replace(nat, formal)

            natural_expr = re.sub(r"\bне\s+(?=\w)", "¬", natural_expr)
            natural_expr = natural_expr.replace("( ", "(").replace(" )", ")")
            while "  " in natural_expr:
                natural_expr = natural_expr.replace("  ", " ")

            natural_expr = natural_expr.replace("если ", "")
            formal_expr = natural_expr.strip()

            # === Построение дерева выражения ===
            def build_expression_tree(expr):
                expr = expr.strip()

                if expr.startswith('(') and expr.endswith(')'):
                    inner = expr[1:-1]
                    depth = 0
                    for i, char in enumerate(inner):
                        if char == '(':
                            depth += 1
                        elif char == ')':
                            depth -= 1
                        if depth < 0:
                            break
                    else:
                        if depth == 0:
                            expr = inner

                operators = ['⇔', '⇒', '∨', '∧', '=', '≠', '⊂', '⊆', '⊄', '∈', '∉', '≥', '≤', '>', '<', '+', '-', '⋅', '/', '↑', '∩', '∪', '∖']

                for op in operators:
                    depth = 0
                    for i in range(len(expr)-1, -1, -1):
                        if expr[i] == ')':
                            depth += 1
                        elif expr[i] == '(':
                            depth -= 1
                        elif depth == 0 and expr[i:i+len(op)] == op:
                            left = expr[:i].strip()
                            right = expr[i+len(op):].strip()
                            return {
                                "operator": op,
                                "left": build_expression_tree(left),
                                "right": build_expression_tree(right)
                            }

                return {"term": expr}

            expression_tree = build_expression_tree(formal_expr)

            # === Сохраняем дерево в JSON ===
            tree_output_path = f"{self.selected_subject}_{formula_type}_expression_tree.json"
            with open(tree_output_path, "w", encoding="utf-8") as f:
                json.dump(expression_tree, f, ensure_ascii=False, indent=2)

            matches = re.findall(r"\(v\d+: [^)]+\)", formal_expr)
            formal_expr_no_vars = formal_expr
            for m in matches:
                formal_expr_no_vars = formal_expr_no_vars.replace(m, "")
            formal_expr_no_vars = formal_expr_no_vars.strip()
            formal_expr = "".join(matches) + formal_expr_no_vars

            if "пустому множеству" in formal_expr:
                formal_expr = formal_expr.replace("пустому множеству", "Ø")

            return formal_expr
        
        list_ontology_model = []

        filename = f"struct_ontology_{self.selected_subject}.json"

        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as file:
                ontology_agreements_list = json.load(file)
        else:
            ontology_agreements_list = []

        for i in ontology_agreements_list:
            list_ontology_model.append(natural_to_formal(i, 'ontology'))

        list_knowledge_model = []

        filename = f"struct_knowledge_{self.selected_subject}.json"

        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as file:
                knowledge_agreements_list = json.load(file)
        else:
            knowledge_agreements_list = []

        for i in knowledge_agreements_list:
            list_knowledge_model.append(natural_to_formal(i, 'knowledge'))

        filename = f"{self.selected_subject}_model.json"

        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as file:
                data = json.load(file)
        else:
            data = {"понятия": [], "онтологические соглашения": [], "знания": []} 

        data["онтологические соглашения"] = []
        data["онтологические соглашения"] = list_ontology_model

        data["знания"] = []
        data["знания"] = list_knowledge_model

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)