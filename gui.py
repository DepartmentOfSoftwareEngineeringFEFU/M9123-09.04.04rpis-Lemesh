import tkinter as tk
from tkinter import messagebox
from tkinter import ttk, scrolledtext
from formula_extractor import FormulaExtractor
from term_extractor import TermExtractor, DimensionalExtractor, ScalarExtractor, SetExtractor, MappingExtractor, UnionExtractor, StructuralExtractor, SequenceExtractor
import sqlite3
from model_generator import ModelGenerator
import ast
import json
import re
import os
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap import Style
from tkinter import font as tkfont

BG_COLOR = "#f4f8ec"
TEXT_FONT = ("Arial", 8)
command_registry = {}

def register_command(name, func):
    command_registry[name] = func

def check_json_serializable(obj, path="root"):
    simple_types = (str, int, float, bool, type(None))
    if isinstance(obj, simple_types):
        return True
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if not check_json_serializable(v, f"{path}['{k}']"):
                return False
        return True
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if not check_json_serializable(item, f"{path}[{i}]"):
                return False
        return True
    else:
        print(f"Ошибка сериализации: объект типа {type(obj).__name__} в {path} не поддерживается для JSON")
        return False

class ConceptsTab:
    def __init__(self, parent, template_options, selected_subject):
        self.parent = parent
        self.template_options = template_options # названия шаблонов
        
        self.templates_entries = [] 
        self.extractor = TermExtractor(strategy=None)

        self.is_save = True
        self.selected_subject = selected_subject # выбранное название предметной области
        self.build_ui()

    def build_ui(self):
        for widget in self.parent.winfo_children():
            widget.destroy()
        concept_frame = ttk.LabelFrame(self.parent, text="Введите определения понятий", padding=10)
        concept_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas_container = ttk.Frame(concept_frame)
        canvas_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(canvas_container, bg="#f4ffe9", highlightthickness=0)
        v_scroll = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(concept_frame, orient="horizontal", command=canvas.xview)

        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.template_container = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self.template_container, anchor="nw")

        def update_scrollbars(event=None):
            canvas.update_idletasks()
            if self.template_container.winfo_reqwidth() > canvas.winfo_width():
                if not h_scroll.winfo_ismapped():
                    h_scroll.pack(side="bottom", fill="x")
            else:
                if h_scroll.winfo_ismapped():
                    h_scroll.pack_forget()

        self.template_container.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            update_scrollbars()
        ))

        # Пример меню шаблонов (можно доработать под свою логику)
        def show_template_menu(event):
            self.template_menu.tk_popup(event.x_root, event.y_root)

        self.template_menu = tk.Menu(self.template_container, tearoff=0, bg="#f0ffe0", fg="black", font=TEXT_FONT)
        for option in self.template_options:
            self.template_menu.add_command(label=option, command=lambda o=option: self.handle_template_choice(o))

        btn_plus = tk.Button(concept_frame, text="+", font=("Arial", 16, "bold"),
                             fg="white", bg="#6abc4f", bd=0, relief="flat",
                             activebackground="#85d362", width=2, height=1)
        btn_plus.pack(anchor="nw", pady=5, padx=5)
        btn_plus.bind("<Button-1>", show_template_menu)

        # Кнопка "Извлечь"
        bottom_frame = ttk.Frame(self.parent)
        bottom_frame.pack(fill="x", side="bottom", pady=(10, 0), padx=10)
        extract_btn = ttk.Button(bottom_frame, text="Извлечь", command=self.extract_action)
        extract_btn.pack(side="right")

        ordered_terms = self.extractor.get_ordered_terms(self.selected_subject)
        
        for table_name, term_id in ordered_terms:
            term_data = self.extractor.get_term_data(table_name, term_id)
            template_type = self.extractor.get_template_type(table_name)
            
            if template_type == 'scalar':
                self.load_scalar_template(term_data)
            elif template_type == 'dimensional':
                self.load_dimensional_template(term_data)
            elif template_type == 'set':
                self.load_set_template(term_data)
            elif template_type == 'mapping':
                self.load_mapping_template(term_data)
            elif template_type == 'union':
                self.load_union_template(term_data)
            elif template_type == 'structural':
                self.load_structural_template(term_data)
            elif template_type == 'sequence':
                self.load_sequence_template(term_data)
        self.is_save = True

    def load_scalar_template(self, term_data: dict):
        # Создаем элементы интерфейса
        self.insert_scalar_template()
        
        # Берем последний добавленный шаблон
        last_template = self.templates_entries[-1]
        
        # Заполняем поля
        last_template['concept'].insert(0, term_data.get('term', ''))
        last_template['values'].insert(0, term_data.get('values_list', ''))
        self.make_entry_autoresize(last_template['values'])
        self.make_entry_autoresize(last_template['concept'])
        self.is_save = True

    def load_dimensional_template(self, term_data: dict):

        self.insert_dimensional_template()

        last_template = self.templates_entries[-1]
        sign_value = ast.literal_eval(term_data.get('volume'))[0]

        last_template['term'].delete(0, tk.END)
        last_template['term'].insert(0, term_data.get('term', ''))
        self.make_entry_autoresize(last_template['term'])

        if sign_value:
            last_template['sign'].set(sign_value)
            last_template['relations_frame'].pack_forget()
            last_template['size_label'].configure(text=' размерных значений')
        else:
            last_template['sign'].set("")
            last_template['relations_frame'].pack(side="left")
            last_template['size_label'].configure(text=' размерных значений, ')

            left = ast.literal_eval(term_data.get('left_clar'))
            if left[0]:
                last_template['left_relation'].set(left[0] + ' ' + left[1])
            else:
                last_template['left_relation'].set(left[1] + ' либо равны')

            # Перезаписываем текст, без вызова placeholder
            last_template['left_term'].delete(0, tk.END)
            last_template['left_term'].insert(0, left[2])

            right = ast.literal_eval(term_data.get('right_clar'))
            if right[0]:
                last_template['right_relation'].set(right[0] + ' ' + right[1])
            else:
                last_template['right_relation'].set(right[1] + ' либо равны')

            last_template['right_term'].delete(0, tk.END)
            last_template['right_term'].insert(0, right[2])
        self.is_save = True

    def load_set_template(self, term_data: dict):

        self.insert_set_template()

        last_template = self.templates_entries[-1]
        last_template['concept'].insert(0, term_data.get('term', ''))
        self.make_entry_autoresize(last_template['concept'])
        # Устанавливаем значение для "непустых"
        if term_data.get('subset_type', ''):
            last_template['non_empty'].set(term_data.get('subset_type', ''))
        else:
            last_template['non_empty'].set("")

        operation = term_data.get('operation')
        if operation:
            description_options = last_template['description_options']
            desc_index = None
            
            # Определяем индекс описания по типу операции
            if operation == 'исключение':
                desc_index = 3
            elif operation == 'пересечение':
                desc_index = 4
            elif operation == 'объединение':
                desc_index = 5

            if desc_index is not None and desc_index < len(description_options):
                desc_value = description_options[desc_index]
                last_template['description'].set(desc_value)
                
                # Принудительно обновляем интерфейс, чтобы сработал trace
                last_template['container'].update_idletasks()
                
                # Получаем актуальные комбобоксы
                dynamic_cbs = last_template.get('dynamic_comboboxes', [])
                
                # Заполняем значениями из term_data
                if len(dynamic_cbs) >= 1:
                    dynamic_cbs[0].set(term_data.get('set1', ''))
                    self.make_entry_autoresize(dynamic_cbs[0])
                if len(dynamic_cbs) >= 2:
                    dynamic_cbs[1].set(term_data.get('set2', ''))
                    self.make_entry_autoresize(dynamic_cbs[1])
            else:
                last_template['description'].set(term_data.get('set1', ''))
                self.make_entry_autoresize(last_template['description'])
        else:
            last_template['description'].set(term_data.get('set1', ''))

        self.is_save = True

    def load_mapping_template(self, term_data: dict):

        self.insert_mapping_template()

        last_template = self.templates_entries[-1]

        # Заполняем основные поля
        last_template['term'].insert(0, term_data.get('term', ''))
        self.make_entry_autoresize(last_template['term'])
        # Устанавливаем значения для домена и кодомена
        domain = term_data.get('domain', '')
        codomain = term_data.get('codomain', '')
        
        # Для Combobox используем прямое присвоение значения
        last_template['domain'].set(domain)
        last_template['codomain'].set(codomain)
        self.is_save = True

    def load_union_template(self, term_data: dict):

        # Создаем элементы интерфейса
        self.insert_union_template()
        
        # Получаем последний добавленный шаблон
        last_template = self.templates_entries[-1]

        # Заполняем основное поле с термином
        last_template['main_term'].insert(0, term_data.get('term', ''))
        self.make_entry_autoresize(last_template['main_term'])
        # Обрабатываем список терминов для объединения
        union_terms = term_data.get('union_terms_list', '')
        if union_terms:
            try:
                # Парсим строку с терминами
                terms_list = [t.strip() for t in union_terms.split(',')]
                
                # Удаляем все существующие комбобоксы (кроме кнопок)
                for cb in last_template['comboboxes']:
                    cb.destroy()
                last_template['comboboxes'].clear()
                
                # Удаляем разделители (если есть)
                for child in last_template['terms_frame'].winfo_children():
                    if isinstance(child, ttk.Label) and child.cget("text") in ['", "', '", "']:
                        child.destroy()
                
                # Загружаем список терминов из БД
                union_values_list = []
                set_terms = self.extractor.load_from_db("set_terms", self.selected_subject, SetExtractor())
                for i in set_terms:
                    union_values_list.append(i['термин'])
                    
                # Добавляем комбобоксы для каждого термина
                for i, term in enumerate(terms_list):
                    # Добавляем разделитель перед каждым новым термином (кроме первого)
                    if i > 0:
                        sep = ttk.Label(last_template['terms_frame'], text='", "', font=TEXT_FONT)
                        sep.pack(side="left", before=last_template['add_btn'])
                    
                    # Создаем комбобокс
                    new_cb = ttk.Combobox(
                        last_template['terms_frame'],
                        values=union_values_list,
                        font=TEXT_FONT,
                        width=15,
                        state="readonly"
                    )
                    new_cb.set(term)
                    
                    # Упаковываем ПЕРЕД кнопкой добавления
                    new_cb.pack(side="left", padx=2, before=last_template['add_btn'])
                    self.make_entry_autoresize(new_cb)
                    last_template['comboboxes'].append(new_cb)

            except Exception as e:
                print(f"Ошибка при загрузке объединенных терминов: {e}")

        self.is_save = True

    def load_structural_template(self, term_data: dict):

        self.insert_structural_template()

        last_template = self.templates_entries[-1]

        # Устанавливаем название понятия
        last_template['term'].insert(0, term_data.get('term', ''))
        self.make_entry_autoresize(last_template['term'])
        # Получаем список атрибутов
        attributes = term_data.get('attrs_list', []).split(', ')

        # Первый атрибут уже установлен в insert_structural_template, заменим его, если данные есть
        if attributes:
            last_template['attributes'][0].insert(0, attributes[0])
        self.make_entry_autoresize(last_template['attributes'][0])
        
        def on_sign_change(event):
            self.make_entry_autoresize(last_template['attributes'][0])
            term = last_template['term'].get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                last_template['term'].delete(0, tk.END)
                last_template['term'].insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                last_template['term'].delete(0, tk.END)
                last_template['term'].insert(0, term)
                return "break"
                
            self.is_save = False

        def add_structural_attribute():
            self.make_entry_autoresize(last_template['attributes'][-1])
            term = last_template['term'].get().strip()
            # if term in self.ontology_terms:
            #     messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
            #     return
            # if term in self.knowledge_terms:
            #     messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
            #     return

            self.is_save = False
            # Проверка ограничения на количество атрибутов
            current_children = last_template['attributes_frame'].winfo_children()
            if len(current_children) >= 19:  # Максимум 10 атрибутов с разделителями
                return

            # Добавление разделителя перед новым атрибутом, если уже есть элементы
            if current_children:
                ttk.Label(last_template['attributes_frame'], text='", "', font=TEXT_FONT).pack(side="left")

            # Создание нового комбобокса
            new_cb = tk.Entry(
                last_template['attributes_frame'],
                font=TEXT_FONT,
                width=15
            )
            new_cb.pack(side="left")

            new_cb.bind("<Button-1>", on_sign_change)

            # Обновление списка атрибутов в соответствующем шаблоне
            for entry in self.templates_entries:
                if entry.get('attributes_frame') == last_template['attributes_frame']:
                    entry['attributes'].append(new_cb)
                    break

        # Добавляем остальные атрибуты
        for attr in attributes[1:]:
            add_structural_attribute()
            last_template['attributes'][-1].insert(0, attr)
            self.make_entry_autoresize(last_template['attributes'][-1])
        self.is_save = True

    def load_sequence_template(self, term_data: dict):

        # Вставляем базовый шаблон последовательности
        self.insert_sequence_template()

        # Получаем последний добавленный шаблон
        last_template = self.templates_entries[-1]

        # Заполняем поле понятия
        concept_entry = last_template.get('term')
        if concept_entry is not None:
            concept_entry.insert(0, term_data.get('term', ''))

        # Определяем имя множества из term_data
        set_name = term_data.get('clarification', '')
        # Заполняем комбобокс множества
        last_template.get('set_combobox').set(set_name)
        self.is_save = True

    def handle_template_choice(self, template_name):
        if template_name == "Шаблон для скалярных величин":
            self.insert_scalar_template()
        elif template_name == "Шаблон для размерных величин":
            self.insert_dimensional_template()
        elif template_name == "Шаблон для величин множеств":
            self.insert_set_template()
        elif template_name == "Шаблон для величин отображений":
            self.insert_mapping_template()
        elif template_name == "Шаблон для объединенных величин":
            self.insert_union_template()
        elif template_name == "Шаблон для структурных величин":
            self.insert_structural_template()
        elif template_name == "Шаблон для величин последовательностей":
            self.insert_sequence_template()
        else:
            # print(f"Выбран шаблон: {template_name}")
            pass

    def load_protected_terms(self):
        ontology_file = f"{self.selected_subject}_ontology_list_terms.json"
        knowledge_file = f"{self.selected_subject}_knowledge_list_terms.json"

        def load_terms(filepath):
            if not os.path.exists(filepath):
                return set()
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()

        self.ontology_terms = load_terms(ontology_file)
        self.knowledge_terms = load_terms(knowledge_file)

    def insert_scalar_template(self):
        self.load_protected_terms()
        self.is_save = False

        template_frame = ttk.Frame(self.template_container)
        template_frame.pack(fill="x", pady=2, padx=10, anchor="w")

        content_frame = ttk.Frame(template_frame)
        content_frame.pack(fill="x", expand=True)

        ttk.Label(content_frame, text='Объем понятия "', font=TEXT_FONT).pack(side="left")

        concept_entry = tk.Entry(content_frame, font=TEXT_FONT, width=15)
        concept_entry.pack(side="left")
        self.make_entry_autoresize(concept_entry)

        ttk.Label(content_frame, text='" состоит из множества скалярных значений:', font=TEXT_FONT).pack(side="left")

        values_container = ttk.Frame(content_frame)
        values_container.pack(side="left", padx=(5, 0))

        values_entry = tk.Entry(values_container, font=TEXT_FONT, width=20)
        values_entry.pack(side="left")
        self.make_entry_autoresize(values_entry)

        self.templates_entries.append({
            'type': 'scalar',
            'container': template_frame,
            'concept': concept_entry,
            'values': values_entry
        })

        def remove_template():

            term = concept_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                return
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                return
            template_frame.destroy()
            self.templates_entries[:] = [e for e in self.templates_entries if e['container'].winfo_exists()]
            self.is_save = False

        btn_remove = tk.Button(values_container, text="X", command=remove_template,
                            font=("Arial", 8, "bold"), fg="white", bg="red", relief="flat")
        btn_remove.pack(side="left", padx=(5, 0))

        def on_edit(event):

            term = concept_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                concept_entry.delete(0, tk.END)
                concept_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                concept_entry.delete(0, tk.END)
                concept_entry.insert(0, term)
                return "break"
            
            self.is_save = False

        concept_entry.bind("<Key>", on_edit)
        values_entry.bind("<Key>", on_edit)

    def insert_dimensional_template(self):

        cb_style = Style('minty')
        cb_style.configure("DCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1)
        
        self.load_protected_terms()
        self.is_save = False

        template_frame = ttk.Frame(self.template_container)
        template_frame.pack(fill="x", pady=2, padx=10, anchor="w")

        content_frame = ttk.Frame(template_frame)
        content_frame.pack(side="left", fill="x", expand=True)

        ttk.Label(content_frame, text='Объем понятия "', font=TEXT_FONT).pack(side="left")

        term_entry = tk.Entry(content_frame, font=TEXT_FONT, width=15)
        term_entry.pack(side="left")
        self.make_entry_autoresize(term_entry)

        ttk.Label(content_frame, text='" состоит из ', font=TEXT_FONT).pack(side="left")

        sign_values = ["", "положительных", "неположительных", "отрицательных", "неотрицательных"]
        
        sign_combobox = tb.Combobox(content_frame, style="DCustomCombobox.TCombobox", values=sign_values, font=TEXT_FONT, width=15, state="readonly")
        sign_combobox.pack(side="left")
        sign_combobox.set(sign_values[0])

        size_label = ttk.Label(content_frame, text=' размерных значений, ', font=TEXT_FONT)
        size_label.pack(side="left")

        relations_frame = ttk.Frame(content_frame)
        relations_frame.pack(side="left")

        ttk.Label(relations_frame, text='элементы которого ', font=TEXT_FONT).pack(side="left")

        left_relation_cb = ttk.Combobox(relations_frame, style="DCustomCombobox.TCombobox", values=["больше либо равны", "строго больше"], font=TEXT_FONT, width=18, state="readonly")
        left_relation_cb.pack(side="left")
        left_relation_cb.set("больше либо равны")

        left_term_entry = tk.Entry(relations_frame, font=TEXT_FONT, width=15)
        left_term_entry.pack(side="left")
        self.make_entry_autoresize(left_term_entry)

        ttk.Label(relations_frame, text=', но ', font=TEXT_FONT).pack(side="left")

        right_relation_cb = ttk.Combobox(relations_frame, style="DCustomCombobox.TCombobox", values=["меньше либо равны", "строго меньше"], font=TEXT_FONT, width=18, state="readonly")
        right_relation_cb.pack(side="left")
        right_relation_cb.set("меньше либо равны")

        right_term_entry = tk.Entry(relations_frame, font=TEXT_FONT, width=15)
        right_term_entry.pack(side="left")
        self.make_entry_autoresize(right_term_entry)

        # Placeholder
        def add_placeholder(entry, placeholder):
            def on_focus_in(event):
                if entry.get() == placeholder:
                    entry.delete(0, tk.END)
                    entry.config(fg='black')
                    self.is_save = False

            def on_focus_out(event):
                if not entry.get():
                    entry.insert(0, placeholder)
                    entry.config(fg='grey')
                    self.is_save = False

            if not entry.get():
                entry.insert(0, placeholder)
                entry.config(fg='grey')
            else:
                entry.config(fg='black')

            entry.bind('<FocusIn>', on_focus_in)
            entry.bind('<FocusOut>', on_focus_out)

        add_placeholder(left_term_entry, '-∞')
        add_placeholder(right_term_entry, '∞')

        # Удаление шаблона
        def remove_template():
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                return
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                return
            template_frame.destroy()
            self.templates_entries[:] = [e for e in self.templates_entries if e['container'].winfo_exists()]
            self.is_save = False

        btn_remove = tk.Button(content_frame, text="X", command=remove_template,
                            font=("Arial", 8, "bold"), fg="white", bg="red", relief="flat")
        btn_remove.pack(side="left", padx=(5, 0))

        # Блокировка редактирования защищённых терминов
        def on_edit(event):
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            self.is_save = False

        left_term_entry.bind("<Key>", on_edit)
        right_term_entry.bind("<Key>", on_edit)
        term_entry.bind("<Key>", on_edit)

        # Изменение состояния интерфейса при выборе знака
        def on_sign_change(event):
            
            selected = sign_combobox.get()

            term = term_entry.get().strip()
            if term in self.ontology_terms:
                sign_combobox.set("")
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                sign_combobox.set("")
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            
            if selected == "":
                relations_frame.pack(side="left")
                size_label.configure(text=' размерных значений, ')
            else:
                relations_frame.pack_forget()
                size_label.configure(text=' размерных значений')
                
            self.is_save = False
            btn_remove.pack_forget()
            btn_remove.pack(side="left", padx=(5, 0))

        def on_rel_change(event):
            
            selected_left = left_relation_cb.get()
            selected_right = right_relation_cb.get()

            term = term_entry.get().strip()
            if term in self.ontology_terms:
                left_relation_cb.set(selected_left)
                right_relation_cb.set(selected_right)
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                left_relation_cb.set(selected_left)
                right_relation_cb.set(selected_right)
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"

        sign_combobox.bind("<Button-1>", on_rel_change)
        sign_combobox.bind("<<ComboboxSelected>>", on_sign_change)
        right_relation_cb.bind("<Button-1>", on_rel_change)
        left_relation_cb.bind("<Button-1>", on_rel_change)
        # Сохраняем структуру   
        self.templates_entries.append({
            'type': 'dimensional',
            'container': template_frame,
            'term': term_entry,
            'sign': sign_combobox,
            'left_relation': left_relation_cb,
            'left_term': left_term_entry,
            'right_relation': right_relation_cb,
            'right_term': right_term_entry,
            'relations_frame': relations_frame,
            'size_label': size_label
        })

    def insert_set_template(self):

        self.load_protected_terms()
        self.is_save = False
        # Создаем контейнер для шаблона
        template_frame = ttk.Frame(self.template_container)
        template_frame.pack(pady=2, padx=10, anchor="w")

        # Основная строка с элементами
        row = ttk.Frame(template_frame)
        row.pack(side="left", fill="x", expand=True)

        # Поле для ввода понятия
        ttk.Label(row, text='Объем понятия "', font=TEXT_FONT).pack(side="left")
        concept_entry = tk.Entry(row, font=TEXT_FONT, width=15)
        concept_entry.pack(side="left")
        self.make_entry_autoresize(concept_entry)

        def on_edit(event):
            term = concept_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                concept_entry.delete(0, tk.END)
                concept_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                concept_entry.delete(0, tk.END)
                concept_entry.insert(0, term)
                return "break"
            self.is_save = False

        concept_entry.bind("<Key>", on_edit)

        def on_sign_change(event):
            
            selected = non_empty_combo.get()

            term = concept_entry.get().strip()
            if term in self.ontology_terms:
                non_empty_combo.set("")
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                concept_entry.delete(0, tk.END)
                concept_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                non_empty_combo.set("")
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                concept_entry.delete(0, tk.END)
                concept_entry.insert(0, term)
                return "break"
                
            self.is_save = False
        
        # Комбобокс для непустых подмножеств
        cb_style = Style('minty')
        cb_style.configure("non_empty_combo.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1)

        ttk.Label(row, text='" состоит из конечных ', font=TEXT_FONT).pack(side="left")
        non_empty_var = tk.StringVar()
        non_empty_combo = ttk.Combobox(
            row, 
            textvariable=non_empty_var, 
            style="non_empty_combo.TCombobox",
            values=["", "непустых"], 
            state="readonly", 
            width=10
        )
        non_empty_combo.set("")
        non_empty_combo.pack(side="left")
        non_empty_combo.bind("<<ComboboxSelected>>", on_sign_change)

        # Динамическая часть с описанием множества
        ttk.Label(row, text='подмножеств ', font=TEXT_FONT).pack(side="left")
        dynamic_wrapper = ttk.Frame(row)
        dynamic_wrapper.pack(side="left")

        # Контейнер для комбобокса с описанием
        description_container = ttk.Frame(dynamic_wrapper)
        description_container.pack(side="left")

        # Опции для выбора описания
        description_options = [
            "названий",
            "вещественных чисел",
            "целых чисел",
            '"термин другого понятия" за исключением подмножеств, которым принадлежат элементы множества "термин другого понятия"',
            "пересечения множеств \"термин другого понятия\" и \"термин другого понятия\"",
            "объединения множеств \"термин другого понятия\" и \"термин другого понятия\"",
        ]
        set_values_list = []
        for i in self.templates_entries:
            try:
                if i['type'] == 'set':
                    set_values_list.append(i['concept'].get())
            except:
                pass

        cb_style.configure("CustomCombobox.TCombobox",
            borderwidth=0,
            relief="flat",
            padding=1, postoffset=(0, 0, 600, 0))
        
        description_options += set_values_list
        description_var = tk.StringVar()
        description_combo = ttk.Combobox(
            description_container,
            style="CustomCombobox.TCombobox",
            textvariable=description_var,
            values=description_options,
            state="readonly",
            width=18
        )
        description_combo.set("")
        description_combo.pack(side="left")

        # Элементы для динамических полей
        label_mnozhestva = ttk.Label(dynamic_wrapper, text="множества ", font=TEXT_FONT)
        subfields_frame = ttk.Frame(dynamic_wrapper)
        subfields_frame.pack(side="left")

        # Сохраняем шаблон сразу, чтобы можно было к нему обратиться из update_dynamic_fields
        self.templates_entries.append({
            'container': template_frame,
            'type': 'set',
            'concept': concept_entry,
            'non_empty': non_empty_var,
            'description': description_var,
            'subfields_frame': subfields_frame,
            'description_options': description_options,
            'dynamic_comboboxes': []
        })

        # Функция обновления динамических полей
        def update_dynamic_fields(*args):
            self.is_save = False
            for widget in subfields_frame.winfo_children():
                widget.destroy()
            description_container.pack_forget()
            label_mnozhestva.pack_forget()

            selected = description_var.get()
            current_template = self.templates_entries[-1]

            font = tkfont.nametofont("TkDefaultFont")
            max_width = max(int(font.measure(v)/8) for v in ["названий", "вещественных чисел", "целых чисел"] + set_values_list)

            cb_style.configure("selectedCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1, postoffset=(0, 0, max_width, 0))

            if selected == "":
                description_container.pack(side="left")
                current_template['dynamic_comboboxes'] = []
                return

            if selected in ["названий", "вещественных чисел", "целых чисел"] + set_values_list:
                label_mnozhestva.pack(side="left", padx=(0, 5))
                description_container.pack(side="left")
                current_template['dynamic_comboboxes'] = []

            elif selected.startswith('"термин другого понятия" за исключением'):
                ttk.Label(subfields_frame, text='множества "', font=TEXT_FONT).pack(side="left")

                cb1 = ttk.Combobox(subfields_frame, style="selectedCombobox.TCombobox", values=set_values_list+["названий", "вещественных чисел", "целых чисел"], width=20)
                cb1.pack(side="left")
                ttk.Label(subfields_frame, text='" за исключением подмножеств, которым принадлежат элементы множества "', font=TEXT_FONT).pack(side="left")
                cb2 = ttk.Combobox(subfields_frame, style="selectedCombobox.TCombobox", values=set_values_list+["названий", "вещественных чисел", "целых чисел"], width=20)
                cb2.pack(side="left")
                ttk.Label(subfields_frame, text='"', font=TEXT_FONT).pack(side="left")
                current_template['dynamic_comboboxes'] = [cb1, cb2]

            elif selected.startswith("пересечения"):
                ttk.Label(subfields_frame, text='пересечения множеств "', font=TEXT_FONT).pack(side="left")
                cb1 = ttk.Combobox(subfields_frame, style="selectedCombobox.TCombobox", values=set_values_list+["названий", "вещественных чисел", "целых чисел"], width=20)
                cb1.pack(side="left")
                ttk.Label(subfields_frame, text='" и "', font=TEXT_FONT).pack(side="left")
                cb2 = ttk.Combobox(subfields_frame, style="selectedCombobox.TCombobox", values=set_values_list+["названий", "вещественных чисел", "целых чисел"], width=20)
                cb2.pack(side="left")
                ttk.Label(subfields_frame, text='"', font=TEXT_FONT).pack(side="left")
                current_template['dynamic_comboboxes'] = [cb1, cb2]

            elif selected.startswith("объединения"):
                ttk.Label(subfields_frame, text='объединения множеств "', font=TEXT_FONT).pack(side="left")
                cb1 = ttk.Combobox(subfields_frame, style="selectedCombobox.TCombobox", values=set_values_list+["названий", "вещественных чисел", "целых чисел"], width=20)
                cb1.pack(side="left")
                ttk.Label(subfields_frame, text='" и "', font=TEXT_FONT).pack(side="left")
                cb2 = ttk.Combobox(subfields_frame, style="selectedCombobox.TCombobox", values=set_values_list+["названий", "вещественных чисел", "целых чисел"], width=20)
                cb2.pack(side="left")
                ttk.Label(subfields_frame, text='"', font=TEXT_FONT).pack(side="left")
                current_template['dynamic_comboboxes'] = [cb1, cb2]

        description_var.trace_add("write", update_dynamic_fields)

        def remove_template():
            term = concept_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                return
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                return
            template_frame.destroy()
            self.templates_entries[:] = [e for e in self.templates_entries if e['container'].winfo_exists()]
            self.is_save = False

        # Кнопка удаления
        btn_remove = tk.Button(
            template_frame, 
            text="X", 
            command=remove_template,
            font=("Arial", 8, "bold"), 
            fg="white", 
            bg="red", 
            relief="flat"
        )
        btn_remove.pack(side="left", padx=(5, 0))

    def insert_mapping_template(self):

        cb_style = Style('minty')
        cb_style.configure("MCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1)

        self.load_protected_terms()
        self.is_save = False
        template_frame = ttk.Frame(self.template_container)
        template_frame.pack(fill="x", pady=2, padx=10, anchor="w")

        content_frame = ttk.Frame(template_frame)
        content_frame.pack(side="left", fill="x", expand=True)

        # Основная строка с вводом термина
        ttk.Label(content_frame, text='Объем понятия "', font=TEXT_FONT).pack(side="left")
        
        term_entry = tk.Entry(content_frame, font=TEXT_FONT, width=15)
        term_entry.pack(side="left")
        self.make_entry_autoresize(term_entry)

        def on_edit(event):
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            self.is_save = False

        term_entry.bind("<Key>", on_edit)
        
        ttk.Label(content_frame, text='" состоит из конечных отображений. Областью определения отображения является "', 
                font=TEXT_FONT).pack(side="left")

        mapping_values_list = []
        for i in self.templates_entries:
            try:
                if i['type'] == 'set':
                    mapping_values_list.append(i['concept'].get())
                elif i['type'] == 'structural':
                    mapping_values_list.append(i['term'].get())
                elif i['type'] == 'union':
                    mapping_values_list.append(i['main_term'].get())
            except:
                pass

        mapping_values_list += ["множество названий", "множество вещественных чисел", "множество целых чисел"]
        # Выпадающий список для области определения
        cb_style = Style('minty')
        cb_style.configure("DMCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1, postoffset=(0,0,100,0))
        
        domain_combobox = ttk.Combobox(content_frame, style="DMCustomCombobox.TCombobox", values=mapping_values_list, 
                                      font=TEXT_FONT, width=18, state="readonly")
        domain_combobox.pack(side="left")
        ttk.Label(content_frame, text='". Областью значений отображения является "', 
                font=TEXT_FONT).pack(side="left")

        # Выпадающий список для области значений
        codomain_combobox = ttk.Combobox(content_frame, style="DMCustomCombobox.TCombobox", values=mapping_values_list, 
                                       font=TEXT_FONT, width=18, state="readonly")
        codomain_combobox.pack(side="left")
        ttk.Label(content_frame, text='".', font=TEXT_FONT).pack(side="left")

        def on_sign_change(event):

            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
                
            self.is_save = False

        def on_change(event):
            self.make_entry_autoresize(domain_combobox)
            self.make_entry_autoresize(codomain_combobox)
        domain_combobox.bind("<Button-1>", on_sign_change)
        codomain_combobox.bind("<Button-1>", on_sign_change)
        domain_combobox.bind("<<ComboboxSelected>>", on_change)
        codomain_combobox.bind("<<ComboboxSelected>>", on_change)

        def remove_template():
            
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                return
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                return

            self.is_save = False
            template_frame.destroy()
            self.templates_entries[:] = [e for e in self.templates_entries if e['container'].winfo_exists()]

        # Кнопка удаления
        btn_remove = tk.Button(content_frame, text="X", command=remove_template,
                             font=("Arial", 8, "bold"), fg="white", bg="red", relief="flat")
        btn_remove.pack(side="left", padx=5)

        # Сохраняем элементы управления
        self.templates_entries.append({
            'type': 'mapping',
            'container': template_frame,
            'term': term_entry,
            'domain': domain_combobox,
            'codomain': codomain_combobox
        })

    def insert_union_template(self):

        cb_style = Style('minty')
        cb_style.configure("UCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1)

        self.load_protected_terms()
        self.is_save = False
        template_frame = ttk.Frame(self.template_container)
        template_frame.pack(fill="x", pady=2, padx=10, anchor="w")

        # Main content area
        content_frame = ttk.Frame(template_frame)
        content_frame.pack(side="left", fill="x", expand=True)

        # Text and entry part
        ttk.Label(content_frame, text='Объем понятия "', font=TEXT_FONT).pack(side="left")
        term_entry = tk.Entry(content_frame, font=TEXT_FONT, width=15)
        term_entry.pack(side="left")
        self.make_entry_autoresize(term_entry)

        def on_edit(event):
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            self.is_save = False

        term_entry.bind("<Key>", on_edit)

        ttk.Label(content_frame, text='" состоит из значений, принадлежащих объединению множеств объемов понятий, обозначенных терминами "',
                font=TEXT_FONT).pack(side="left")

        # Dynamic terms container
        terms_frame = ttk.Frame(content_frame)
        terms_frame.pack(side="left", fill="x", expand=True)
        
        union_values_list = []
        for i in self.templates_entries:
            try:
                if i['type'] in ['scalar', 'set']:
                    union_values_list.append(i['concept'].get())
                if i['type'] == 'dimensional':
                    union_values_list.append(i['term'].get())
            except:
                pass
        
        # Initial combobox
        initial_combobox = ttk.Combobox(
            terms_frame,
            values=union_values_list,
            style="UCustomCombobox.TCombobox",
            font=TEXT_FONT,
            width=15,
            state="readonly"
        )
        initial_combobox.pack(side="left", padx=2)
        self.make_entry_autoresize(initial_combobox)

        def on_sign_change(event):

            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
                
            self.is_save = False

        initial_combobox.bind("<Button-1>", on_sign_change)

        def add_union_term():

            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                return
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                return

            self.is_save = False
            if len(terms_frame.winfo_children()) >= 19:
                return

            # Находим запись текущего шаблона
            current_entry = None
            for entry in self.templates_entries:
                if 'terms_frame' in entry and entry['terms_frame'] == terms_frame:
                    current_entry = entry
                    break

            if not current_entry:
                return

            # Добавляем разделитель только если уже есть комбобоксы (кроме первого)
            if len(current_entry['comboboxes']) >= 1:
                sep = ttk.Label(terms_frame, text='", "', font=TEXT_FONT)
                # Упаковываем разделитель ПЕРЕД кнопкой добавления
                sep.pack(side="left", before=current_entry['add_btn'])

            # Создаем новый комбобокс
            new_cb = ttk.Combobox(
                terms_frame,
                values=union_values_list,
                style="UCustomCombobox.TCombobox",
                font=TEXT_FONT,
                width=15,
                state="readonly"
            )
            # Упаковываем комбобокс ПЕРЕД кнопкой добавления
            new_cb.pack(side="left", before=current_entry['add_btn'])

            new_cb.bind("<Button-1>", on_sign_change)

            self.make_entry_autoresize(new_cb)
            # Обновляем список комбобоксов в шаблоне
            current_entry['comboboxes'].append(new_cb)

        # Создаем кнопки и упаковываем их ВНУТРЬ terms_frame
        btn_add = tk.Button(
            terms_frame,  # Родитель - terms_frame
            text="+",
            font=("Arial", 8, "bold"),
            fg="white",
            bg="#6abc4f",
            relief="flat",
            command=add_union_term
        )
        btn_add.pack(side="left", padx=2)

        def remove_template():
            
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                return
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                return

            self.is_save = False
            template_frame.destroy()
            self.templates_entries[:] = [e for e in self.templates_entries if e['container'].winfo_exists()]

        btn_remove = tk.Button(
            terms_frame,  # Родитель - terms_frame
            text="X",
            command=remove_template,
            font=("Arial", 8, "bold"),
            fg="white",
            bg="red",
            relief="flat"
        )
        btn_remove.pack(side="left", padx=2)

        self.templates_entries.append({
            'type': 'union',
            'container': template_frame,
            'main_term': term_entry,
            'terms_frame': terms_frame,
            'comboboxes': [initial_combobox],
            'add_btn': btn_add,       # Сохраняем ссылки на кнопки
            'remove_btn': btn_remove
        })
  
    def insert_structural_template(self):

        cb_style = Style('minty')
        cb_style.configure("StructCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1)
    
        self.load_protected_terms()
        self.is_save = False
        # Создание фрейма для шаблона
        template_frame = ttk.Frame(self.template_container)
        template_frame.pack(pady=2, padx=10, anchor="w")

        # Основной контейнер для содержимого
        content_frame = ttk.Frame(template_frame)
        content_frame.pack(side="left", fill="x", expand=True)

        # Ввод термина понятия
        ttk.Label(content_frame, text='Объем понятия "', font=TEXT_FONT).pack(side="left")
        term_entry = tk.Entry(content_frame, font=TEXT_FONT, width=15)
        term_entry.pack(side="left")
        self.make_entry_autoresize(term_entry)

        def on_edit(event):
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            self.is_save = False

        term_entry.bind("<Key>", on_edit)

        ttk.Label(content_frame, text='" состоит из конечных подмножеств структурных объектов, имеющих одну и ту же структуру. Атрибутами этих структурных объектов являются "', 
                font=TEXT_FONT).pack(side="left")

        # Контейнер для атрибутов с возможностью добавления
        attributes_frame = ttk.Frame(content_frame)
        attributes_frame.pack(side="left")

        attr_var = tk.StringVar()
        # Начальный комбобокс для первого атрибута
        initial_cb = tk.Entry(
            attributes_frame,
            # style="StructCustomCombobox.TCombobox",
            textvariable=attr_var,
            font=TEXT_FONT,
            width=15
        )
        initial_cb.pack(side="left")
        self.make_entry_autoresize(initial_cb)

        ttk.Label(content_frame, text='" ', font=TEXT_FONT).pack(side="left")

        def on_sign_change(event):
                
            self.is_save = False

        initial_cb.bind("<Button-1>", on_sign_change)

        def on_attr_change(*args):
            self.is_save = False

        # Назначение "трейса"
        attr_var.trace_add("write", on_attr_change)
        
        # Фрейм для кнопок управления справа
        btn_frame = ttk.Frame(template_frame, relief="flat")
        btn_frame.pack(side="left", padx=5)

        def add_structural_attribute():

            self.is_save = False
            # Проверка ограничения на количество атрибутов
            current_children = attributes_frame.winfo_children()
            if len(current_children) >= 19:  # Максимум 10 атрибутов с разделителями
                return

            # Добавление разделителя перед новым атрибутом, если уже есть элементы
            if current_children:
                ttk.Label(attributes_frame, text='", "', font=TEXT_FONT).pack(side="left")

            # Создание нового комбобокса
            new_cb = tk.Entry(
                attributes_frame,
                # style="StructCustomCombobox.TCombobox",
                font=TEXT_FONT,
                width=15
            )
            new_cb.pack(side="left")
            self.make_entry_autoresize(new_cb)

            new_cb.bind("<Button-1>", on_sign_change)

            # Обновление списка атрибутов в соответствующем шаблоне
            for entry in self.templates_entries:
                if entry.get('attributes_frame') == attributes_frame:
                    entry['attributes'].append(new_cb)
                    break

        # Кнопка добавления нового атрибута
        btn_add = tk.Button(
            btn_frame,
            text="+",
            font=("Arial", 8, "bold"),
            fg="white",
            bg="#6abc4f",
            relief="flat",
            command=add_structural_attribute
        )
        btn_add.pack(side="left", padx=2, pady=2)

        def remove_template():
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                return
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                return
            template_frame.destroy()
            self.templates_entries[:] = [e for e in self.templates_entries if e['container'].winfo_exists()]
            self.is_save = False

        # Кнопка удаления шаблона
        btn_remove = tk.Button(
            btn_frame,
            text="X",
            command=remove_template,
            font=("Arial", 8, "bold"),
            fg="white",
            bg="red",
            relief="flat"
        )
        btn_remove.pack(side="right", padx=2, pady=2)

        # Сохранение элементов в списке для последующего извлечения
        self.templates_entries.append({
            'type': 'structural',
            'container': template_frame,
            'term': term_entry,
            'attributes_frame': attributes_frame,
            'attributes': [initial_cb]  # Начальный комбобокс
        })

    def insert_sequence_template(self):

        cb_style = Style('minty')
        cb_style.configure("SeqCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1)

        self.load_protected_terms()
        self.is_save = False
        # Создаем контейнер для шаблона
        template_frame = ttk.Frame(self.template_container)
        template_frame.pack(pady=2, padx=10, anchor="w")

        # Основное содержимое
        content_frame = ttk.Frame(template_frame)
        content_frame.pack(side="left", fill="x", expand=True)

        # Ввод термина понятия
        ttk.Label(content_frame, text='Объем понятия "', font=TEXT_FONT).pack(side="left")
        term_entry = tk.Entry(content_frame, font=TEXT_FONT, width=15)
        term_entry.pack(side="left")
        self.make_entry_autoresize(term_entry)
        
        def on_edit(event):
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            self.is_save = False

        term_entry.bind("<Key>", on_edit)

        # Текстовая часть шаблона
        ttk.Label(content_frame, text='" состоит из бесконечного множества конечных последовательностей, элементы каждой последовательности принадлежат конечному множеству "', 
                font=TEXT_FONT).pack(side="left")
        seq_values_list = []
        for i in self.templates_entries:
            try:
                if i['type'] == 'set':
                    seq_values_list.append(i['concept'].get())
            except:
                pass
        # Выбор множества
        set_combobox = ttk.Combobox(
            content_frame,
            values=seq_values_list,
            style="SeqCustomCombobox.TCombobox",
            font=TEXT_FONT,
            width=15,
            state="readonly"
        )
        set_combobox.pack(side="left")
        set_combobox.set("")

        def on_sign_change(event):

            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                term_entry.delete(0, tk.END)
                term_entry.insert(0, term)
                return "break"
                
            self.is_save = False

        set_combobox.bind("<Button-1>", on_sign_change)

        # Закрывающая кавычка
        ttk.Label(content_frame, text='".', font=TEXT_FONT).pack(side="left")

        def remove_template():
            term = term_entry.get().strip()
            if term in self.ontology_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении онтологических соглашений и не может быть изменен")
                return
            if term in self.knowledge_terms:
                messagebox.showerror("Ошибка", "Термин данного понятия используется при определении знаний и не может быть изменен")
                return
            template_frame.destroy()
            self.templates_entries[:] = [e for e in self.templates_entries if e['container'].winfo_exists()]
            self.is_save = False

        # Кнопка удаления
        btn_remove = tk.Button(
            template_frame,
            text="X",
            command=remove_template,
            font=("Arial", 8, "bold"),
            fg="white",
            bg="red",
            relief="flat"
        )
        btn_remove.pack(side="right", padx=5)

        # Сохраняем элементы управления
        self.templates_entries.append({
            'type': 'sequence',
            'container': template_frame,
            'term': term_entry,
            'set_combobox': set_combobox
        })

    def make_entry_autoresize(self, entry, min_chars=10, padding=2):
        def resize(event=None):
            content = entry.get()
            entry.config(width=max(len(content) + padding, min_chars))
        entry.bind('<KeyRelease>', resize)
        resize()

    def extract_action(self):
        current_terms = []
        terms_list = []

        mapping_info = {}

        def get_term(tpl):
            tpl_type = tpl.get('type')
            if tpl_type == 'scalar':
                return tpl['concept'].get().strip()
            elif tpl_type in ('dimensional', 'mapping', 'structural', 'sequence'):
                return tpl['term'].get().strip()
            elif tpl_type == 'set':
                return tpl['concept'].get().strip()
            elif tpl_type == 'union':
                return tpl['main_term'].get().strip()
            return ""

        # 1. Сбор и валидация терминов
        for tpl in self.templates_entries:
            if not tpl['container'].winfo_exists():
                continue

            term = get_term(tpl)
            if tpl.get('type') == 'scalar' and tpl['values'].get().strip() == '':
                messagebox.showerror("Пустое определение объема", "Перед сохранением необходимо определить объемы всех понятий")
                return False
            
            # Проверка для структурного шаблона: заполненность атрибутов
            if tpl.get('type') == 'structural':
                attributes = tpl.get('attributes', [])
                for i, attr_entry in enumerate(attributes, 1):
                    attr_value = attr_entry.get().strip()
                    if not attr_value:
                        # Определяем основной термин для сообщения об ошибке
                        main_term = tpl['term'].get().strip() or "<без названия>"
                        messagebox.showerror(
                            "Пустое определение объема",
                            f"Для понятия '{main_term}' необходимо заполнить все атрибуты в описании объема"
                        )
                        return False

            if tpl.get('type') == 'set':
                desc = tpl['description'].get().strip()

                if desc == '':
                    messagebox.showerror("Пустое определение объема", f"Для понятия '{term}' необходимо выбрать описание подмножеств.")
                    return False

                # Проверка: если выбраны шаблоны с "термин другого понятия", то убедиться, что все динамические поля заполнены
                if any(desc.startswith(keyword) for keyword in [
                    '"термин другого понятия"',
                    "пересечения",
                    "объединения"
                ]):
                    for cb in tpl.get('dynamic_comboboxes', []):
                        if cb.get().strip() == '':
                            messagebox.showerror(
                                "Пустое определение объема",
                                f"Для понятия '{term}' необходимо заполнить все термы в описании объема"
                            )
                            return False
            if tpl.get('type') == 'mapping':
                domain_val = tpl['domain'].get().strip()
                codomain_val = tpl['codomain'].get().strip()
                
                if not domain_val or not codomain_val:
                    main_term = term or "<без названия>"
                    messagebox.showerror(
                        "Пустое определение объема",
                        f"Для понятия '{main_term}' необходимо заполнить область определения и область значений"
                    )
                    return False
            if tpl.get('type') == 'union':
                
                # Проверка всех комбобоксов
                for i, cb in enumerate(tpl.get('comboboxes', []), 1):
                    if not cb.get().strip():
                        messagebox.showerror(
                            "Пустое определение объема",
                            f"Для понятия '{term}' необходимо заполнить все термы в описании объема"
                        )
                        return False
                    
            if not term:
                messagebox.showerror("Пустой термин", "Перед сохранением необходимо ввести все термины")
                return False
            
            if tpl.get('type') == 'mapping':
                domain = tpl['domain'].get().strip()
                codomain = tpl['codomain'].get().strip()
                mapping_info[term] = (domain, codomain)

            terms_list.append(term)

        for tpl in self.templates_entries:
            if not tpl['container'].winfo_exists() or tpl.get('type') != 'structural':
                continue
                
            structural_term = tpl['term'].get().strip() or "<без названия>"
            attributes = tpl.get('attributes', [])
            
            # Проверка заполненности атрибутов
            for i, attr_entry in enumerate(attributes, 1):
                attr_value = attr_entry.get().strip()
                if not attr_value:
                    messagebox.showerror(
                        "Пустой атрибут",
                        f"В структурном понятии '{structural_term}' не заполнен атрибут #{i}"
                    )
                    return False
            
            # Проверка соответствия атрибутов
            for attr_entry in attributes:
                attr_value = attr_entry.get().strip()
                
                # Проверка 1: существует ли отображение с таким термином
                if attr_value not in mapping_info:
                    messagebox.showerror(
                        "Несоответствие атрибута",
                        f"Атрибут '{attr_value}' в структурном понятии '{structural_term}'\n"
                        "не соответствует ни одному термину отображения.\n\n"
                        "Каждый атрибут должен быть объявлен как отдельное отображение."
                    )
                    return False
                
                # Проверка 2: область определения отображения == термину структурного понятия
                domain, codomain = mapping_info[attr_value]
                if domain != structural_term:
                    messagebox.showerror(
                        "Несоответствие области определения",
                        f"Отображение '{attr_value}' должно иметь область определения '{structural_term}',\n"
                        f"но указана область '{domain}'.\n\n"
                        f"Исправьте отображение или измените атрибут в понятии '{structural_term}'."
                    )
                    return False
            
        if len(terms_list) != len(set(terms_list)):
            messagebox.showerror("Дублирующиеся термины", "Удалите дублирующиеся термины и повторите попытку")
            return False

        # 2. Обработка шаблонов
        for tpl in self.templates_entries:
            if not tpl['container'].winfo_exists():
                continue

            tpl_type = tpl.get('type')
            strategy = None
            line = ""

            if tpl_type == 'scalar':
                concept = tpl['concept'].get().strip()
                values = tpl['values'].get().strip()
                line = f'Объем понятия {concept} состоит из множества скалярных значений: {values}'
                strategy = ScalarExtractor()

            elif tpl_type == 'dimensional':
                term = tpl['term'].get().strip()
                sign = tpl['sign'].get()
                left_rel = tpl['left_relation'].get()
                left_term = tpl['left_term'].get().strip()
                right_rel = tpl['right_relation'].get()
                right_term = tpl['right_term'].get().strip()

                if sign:
                    line = f'Объем понятия {term} состоит из {sign} размерных значений'
                else:
                    line = f'Объем понятия {term} состоит из {sign}размерных значений, элементы которого {left_rel} {left_term}, но {right_rel} {right_term}'
                strategy = DimensionalExtractor()

            elif tpl_type == 'set':
                concept = tpl['concept'].get().strip()
                non_empty = tpl['non_empty'].get()
                description = tpl['description'].get()
                subfield_values = [
                    w.get().strip() for w in tpl['subfields_frame'].winfo_children() if isinstance(w, ttk.Combobox)
                ]

                line = f'Объем понятия {concept} состоит из '
                if non_empty:
                    line += f'конечных {non_empty} подмножеств '
                else:
                    line += 'конечных подмножеств '

                if description in ["названий", "вещественных чисел", "целых чисел", ""]:
                    line += f'множества {description}' if description else line.rstrip()
                elif description.startswith('"термин другого понятия" за исключением') and len(subfield_values) >= 2:
                    a, b = subfield_values[:2]
                    line += f'множества {a} за исключением подмножеств, которым принадлежат элементы множества {b}'
                elif description.startswith("пересечения") and len(subfield_values) >= 2:
                    a, b = subfield_values[:2]
                    line += f'пересечения множеств {a} и {b}'
                elif description.startswith("объединения") and len(subfield_values) >= 2:
                    a, b = subfield_values[:2]
                    line += f'объединения множеств {a} и {b}'
                else:
                    line += f'множества {description}' if description else line.rstrip()
                strategy = SetExtractor()

            elif tpl_type == 'mapping':
                term = tpl['term'].get().strip()
                domain = tpl['domain'].get().strip()
                codomain = tpl['codomain'].get().strip()
                line = f'Объем понятия {term} состоит из конечных отображений. Областью определения отображения является {domain}. Областью значений отображения является {codomain}.'
                strategy = MappingExtractor()

            elif tpl_type == 'union':
                main_term = tpl['main_term'].get().strip()
                terms = [cb.get().strip() for cb in tpl['comboboxes']]
                line = f'Объем понятия {main_term} состоит из значений, принадлежащих объединению множеств объемов понятий, обозначенных терминами {", ".join(terms)}.'
                strategy = UnionExtractor()

            elif tpl_type == 'structural':
                term = tpl['term'].get().strip()
                attrs = [cb.get() for cb in tpl['attributes']]
                line = f'Объем понятия {term} состоит из конечных подмножеств структурных объектов, имеющих одну и ту же структуру. Атрибутами этих структурных объектов являются {", ".join(attrs)}'
                strategy = StructuralExtractor()

            elif tpl_type == 'sequence':
                term = tpl['term'].get().strip()
                selected_set = tpl['set_combobox'].get().strip()
                line = f'Объем понятия {term} состоит из бесконечного множества конечных последовательностей, элементы которых принадлежат множеству {selected_set}.'
                strategy = SequenceExtractor()

            if not line or not strategy:
                continue

            self.extractor.set_strategy(strategy)
            result = self.extractor.extract_terms(line)
            term = result.get('термин', '').strip()
            if not term:
                continue

            strategy_name = strategy.__class__.__name__
            table = self.extractor.table_map[strategy_name][0]
            current_terms.append((table, term))
            self.extractor.save_to_db(result, self.selected_subject)

        # 3. Удаление отсутствующих терминов
        domain_id = self.extractor._get_or_create_domain_id(self.selected_subject)
        existing = self.extractor.get_all_terms_for_domain(domain_id)
        to_delete = [ (table, term) for (table, term) in existing if (table, term) not in current_terms ]
        for table, term in to_delete:
            self.extractor.delete_term(domain_id, table, term)

        self.extractor.conn.commit()
        self.is_save = True
        return True

class FormulaTab:

    def load_ui(self, formula_type):
        filename = f"ui_state_{formula_type}_{self.selected_subject}.json"
        if not os.path.exists(filename):
            print(f"[load_ui] Файл не найден: {filename}. Загрузка пропущена.")
            return

        with open(filename, encoding="utf-8") as f:
            data = json.load(f)

        for child in self.template_container.winfo_children():
            child.destroy()

        self.deserialize_widget(data, self.template_container)

        # Восстанавливаем зависимости после загрузки всех виджетов
        for widget_id, widget in self.widget_id_map.items():
            depends_on_id = getattr(widget, 'depends_on_id', None)
            widget.depends_on = self.widget_id_map.get(depends_on_id) if depends_on_id else None

        # Восстанавливаем логику формул и поведения
        for widget in self.widget_id_map.values():
            formula_type = getattr(widget, 'formula_type', None)
            role = getattr(widget, 'role', None)
            needs_logic_restore = getattr(widget, 'needs_logic_restore', False)

            if formula_type == "scalar":
                self.setup_scalar_formula_logic(widget)
            elif formula_type in ["dimensional", "dimensional_operation"]:
                self.setup_combobox_operand_logic(widget, self.on_operand_selected)

            if needs_logic_restore:
                if role == "dimensional_term":
                    self.setup_dimensional_term_logic(widget)
                elif role == "operation_selector":
                    self.restore_operation_selector(widget)

        # Очищаем карту после восстановления
        self.widget_id_map = {}

    def setup_combobox_operand_logic(self, frame, handler):

        if not frame.winfo_exists():
            return

        for child in frame.winfo_children():
            if not child.winfo_exists():
                continue
            if isinstance(child, ttk.Combobox) and hasattr(child, 'operand_type') and hasattr(child, 'needs_logic_restore'):
                is_main_left = child.operand_type == "left"
                child.bind("<<ComboboxSelected>>", 
                        lambda e, c=child, p=child.master, il=is_main_left: handler(c, p, il))

    def restore_operation_selector(self, combobox):
        """Восстанавливает логику для комбобокса выбора операции"""
        # Проверяем существование виджета
        if not combobox.winfo_exists():
            return
            
        # Получаем сохраненные параметры
        operand_type = getattr(combobox, 'operand_type', "left")
        is_main_left = operand_type == "left"
        parent_frame = combobox.master
        
        # Удаляем старые привязки
        if combobox.bind("<<ComboboxSelected>>"):
            combobox.unbind("<<ComboboxSelected>>")
        
        # Восстанавливаем привязку
        combobox.bind("<<ComboboxSelected>>", 
            lambda e, c=combobox, p=parent_frame, il=is_main_left: self.create_operation_structure(c, p, il))

    def setup_scalar_formula_logic(self, frame):
        """Восстанавливает логику для скалярных формул"""
        # Поиск комбобоксов по ролям
        left_term_cb = None
        right_value_cb = None
        
        for child in frame.winfo_children():
            if hasattr(child, 'role'):
                if child.role == "left_term":
                    left_term_cb = child
                elif child.role == "right_value":
                    right_value_cb = child
        
        if not left_term_cb or not right_value_cb:
            return

        # Убираем старые привязки, если они есть
        for event in ["<Button-1>", "<<ComboboxSelected>>"]:
            if left_term_cb.bind(event):
                left_term_cb.unbind(event)
            if right_value_cb.bind(event):
                right_value_cb.unbind(event)

        # Устанавливаем функции обновления
        def refresh_terms(event=None):
            scalar_terms = self.extractor.load_from_db("scalar_terms", self.selected_subject, ScalarExtractor())
            term_names = [term['термин'] for term in scalar_terms]

            current = left_term_cb.get()
            left_term_cb['values'] = term_names
            left_term_cb.set(current if current in term_names else '')
            
            # Обновляем значения в правом комбобоксе
            update_values()

        def update_values(event=None):
            if not left_term_cb.get():
                right_value_cb['values'] = []
                return
            right_value_cb.set('')
            scalar_terms = self.extractor.load_from_db("scalar_terms", self.selected_subject, ScalarExtractor())
            selected_term = left_term_cb.get()
            
            for term in scalar_terms:
                if term['термин'] == selected_term:
                    values = term.get('Уточнение объема', [])
                    right_value_cb['values'] = values
                    if values and not right_value_cb.get():
                        right_value_cb.current(0)
                    return
            
            right_value_cb['values'] = []

        # Привязываем обработчики
        left_term_cb.bind("<Button-1>", refresh_terms)
        left_term_cb.bind("<<ComboboxSelected>>", update_values)
        right_value_cb.bind("<Button-1>", refresh_terms)
        
        # Инициируем начальную загрузку
        refresh_terms()
        
        # Помечаем, что логика восстановлена
        frame.logic_restored = True

    def deserialize_widget(self, data, parent):
        widget_type = data["type"]
        widget = None
        widget_id = None  # Для отслеживания зависимостей
        cb_style = Style('minty')
        cb_style.configure("deserializeCustomCombobox.TCombobox",
            borderwidth=0,
            relief="flat",
            padding=1)
        if widget_type == "TLabel":
            widget = ttk.Label(parent, text=data.get("text", ""))
        elif widget_type == "TCombobox":
            widget = ttk.Combobox(parent, style="deserializeCustomCombobox.TCombobox", values=data.get("values", []), state="readonly")
            widget.set(data.get("selected", ""))
            
            # Восстанавливаем специальные атрибуты
            if 'operand_type' in data:
                widget.operand_type = data['operand_type']
            if 'role' in data:
                widget.role = data['role']
                
            # Помечаем для восстановления логики
            if 'role' in data or 'operand_type' in data:
                widget.needs_logic_restore = True

        elif widget_type == "TEntry":
            widget = ttk.Entry(parent)
            widget.insert(0, data.get("text", ""))
        elif widget_type == "Button":
            cmd_name = data.get("command_name")
            text = data.get("text", "")

            if text == "X":
                # Для кнопок удаления сохраняем ID родительского фрейма
                cmd_name = f"remove_template_{id(parent)}"
                register_command(cmd_name, lambda w=parent: w.destroy())
                
                widget = tk.Button(parent, text="X", command=command_registry[cmd_name],
                                font=("Arial", 8, "bold"), fg="white", bg="red", relief="flat")
                widget._command_name = cmd_name
            else:
                cmd_func = command_registry.get(cmd_name)
                widget = tk.Button(parent, text=text, command=cmd_func)
                if cmd_name:
                    widget._command_name = cmd_name
        elif widget_type == "Menu":
            widget = tk.Menu(parent, tearoff=0, bg="#f0ffe0", fg="black", font=TEXT_FONT)
            widget._menu_commands = {}
            for i, item in enumerate(data.get("menu_items", [])):
                cmd_name = item.get("command_name")
                cmd_func = command_registry.get(cmd_name)
                if item["type"] == "command":
                    widget.add_command(label=item["label"], command=cmd_func)
                    widget._menu_commands[i] = cmd_name
        elif widget_type == "TFrame":
            widget = ttk.Frame(parent)
        elif widget_type == "TLabelframe":
            widget = ttk.LabelFrame(parent, text=data.get("text", ""))
        else:
            print(f"[deserialize_widget] Пропущен неизвестный виджет: {widget_type}")
            return None

        # Восстанавливаем специальные атрибуты
        if 'formula_type' in data:
            widget.formula_type = data['formula_type']
            
        if 'role' in data:
            widget.role = data['role']
            
        if 'depends_on_id' in data:
            # Сохраняем ID для последующего восстановления зависимостей
            widget.depends_on_id = data['depends_on_id']
            
        # Сохраняем ID виджета для восстановления зависимостей
        widget_id = id(widget)

        # Применяем layout
        layout = data.get("layout")
        if layout:
            try:
                widget.pack(**layout)
            except Exception as e:
                print(f"[deserialize_widget] Ошибка применения layout: {e}")
        else:
            if widget_type != "Menu":  # Меню не пакуются
                widget.pack()

        # Рекурсивно воссоздаем дочерние виджеты
        for child_data in data.get("children", []):
            child_widget = self.deserialize_widget(child_data, widget)
            if child_widget:
                # Сохраняем ссылку на родителя
                child_widget.parent_widget = widget

        if widget_id:
            self.widget_id_map[widget_id] = widget
            
        return widget
    
    def insert_kernel_formula(self, parent_frame):
        main_frame = ttk.Frame(parent_frame)
        main_frame.pack(anchor="w")

        ttk.Label(main_frame, text="(").pack(side="left")
        inner_frame = ttk.Frame(main_frame)
        inner_frame.pack(side="left")
        ttk.Label(main_frame, text=")").pack(side="left")

        options = [
            "левая_формула и правая_формула",
            "левая_формула или правая_формула",
            "если левая_формула то правая_формула",
            "левая_формула тогда и только тогда, когда правая_формула"
        ]

        cb_style = Style('minty')
        cb_style.configure("insertStandarddCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1, postoffset=(0, 0, 210, 0))
        
        combo = ttk.Combobox(inner_frame, style="insertStandarddCustomCombobox.TCombobox", values=options, state="readonly")
        combo.pack()
        combo.bind("<<ComboboxSelected>>", 
            lambda e: self.on_kernel_option_selected(inner_frame, combo))

    def insert_standard_formula(self, parent_frame):
        main_frame = ttk.Frame(parent_frame)
        main_frame.pack(anchor="w")

        ttk.Label(main_frame, text="(").pack(side="left")
        inner_frame = ttk.Frame(main_frame)
        inner_frame.pack(side="left")
        ttk.Label(main_frame, text=")").pack(side="left")

        base_options = [
            "Формулы для скалярных значений",
            "Формулы для размерных значений",
            "Формулы для множеств"
        ]

        cb_style = Style('minty')
        cb_style.configure("insertStandardCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1, postoffset=(0, 0, 80, 0))

        combo = ttk.Combobox(inner_frame, style="insertStandardCustomCombobox.TCombobox", values=base_options, state="readonly")
        combo.pack()
        combo.bind("<<ComboboxSelected>>", lambda e: self.on_standard_formula_selected(inner_frame, combo))

    def on_standard_formula_selected(self, parent_frame, combo):
        selected = combo.get()
        combo.destroy()

        if selected == "Формулы для скалярных значений":
            options = [
                '"левый термин" равен "значение"',
                '"левый термин" не равен "значение"'
            ]

            cb_style = Style('minty')
            cb_style.configure("onScStandardCustomCombobox.TCombobox",
                    borderwidth=0,
                    relief="flat",
                    padding=1, postoffset=(0, 0, 80, 0))
        
            new_combo = ttk.Combobox(parent_frame, style="onScStandardCustomCombobox.TCombobox", values=options, state="readonly")
            new_combo.pack()
            new_combo.bind("<<ComboboxSelected>>", lambda e: self.insert_scalar_formula(parent_frame, new_combo))

        elif selected == "Формулы для размерных значений":
            options = [
                '"левый терм" меньше "правый терм"',
                '"левый терм" больше "правый терм"',
                '"левый терм" больше либо равен "правый терм"',
                '"левый терм" меньше либо равен "правый терм"',
                '"левый терм" равен "правый терм"',
                '"левый терм" не равен "правый терм"'
            ]

            cb_style = Style('minty')
            cb_style.configure("onDimStandardCustomCombobox.TCombobox",
                    borderwidth=0,
                    relief="flat",
                    padding=1, postoffset=(0, 0, 150, 0))

            new_combo = ttk.Combobox(parent_frame, style="onDimStandardCustomCombobox.TCombobox", values=options, state="readonly")
            new_combo.pack()
            new_combo.bind("<<ComboboxSelected>>", lambda e: self.insert_dimensional_formula(parent_frame, new_combo))

        elif selected == "Формулы для множеств":
            options = [
                '"левый терм" принадлежит "правое множество"',
                '"левый терм" не принадлежит "правое множество"',
                '"левое множество" является подмножеством "правое множество"',
                '"левое множество" является подмножеством либо равно "правое множество"',
                '"левое множество" не является подмножеством "правое множество"',
                '"левое множество" равно "правое множество"',
                '"левое множество" не равно "правое множество"'
            ]

            cb_style = Style('minty')
            cb_style.configure("onSetStandardCustomCombobox.TCombobox",
                    borderwidth=0,
                    relief="flat",
                    padding=1, postoffset=(0, 0, 310, 0))
            
            new_combo = ttk.Combobox(parent_frame, style="onSetStandardCustomCombobox.TCombobox", values=options, state="readonly")
            new_combo.pack()
            new_combo.bind("<<ComboboxSelected>>", lambda e: self.insert_set_formula(parent_frame, new_combo))

    def insert_scalar_formula(self, parent_frame, combo):
        selected = combo.get()
        combo.destroy()

        cb_style = Style('minty')
        cb_style.configure("SсCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1)

        frame = ttk.Frame(parent_frame)
        frame.pack()
        frame.formula_type = "scalar"  # Помечаем тип формулы

        # Левый термин
        left_term_cb = ttk.Combobox(frame, style="SсCustomCombobox.TCombobox", values=[], state="readonly")
        left_term_cb.pack(side="left")
        left_term_cb.role = "left_term"  # Помечаем роль
        
        # Оператор
        if "равен" in selected: 
            op_text = " равен " if "не" not in selected else " не равен "
            ttk.Label(frame, text=op_text).pack(side="left")
        
        # Правый термин
        right_value_cb = ttk.Combobox(frame, style="SсCustomCombobox.TCombobox", values=[], state="readonly")
        right_value_cb.pack(side="left")
        right_value_cb.role = "right_value"  # Помечаем роль
        right_value_cb.depends_on = left_term_cb  # Устанавливаем зависимость
        
        # Устанавливаем логику обновления
        self.setup_scalar_formula_logic(frame)

    def insert_dimensional_formula(self, parent_frame, combo):
        selected = combo.get()
        combo.destroy()

        cb_style = Style('minty')
        cb_style.configure("SdCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1)

        frame = ttk.Frame(parent_frame)
        frame.pack()
        frame.formula_type = "dimensional"  # Помечаем тип формулы
        
        # Определяем оператор
        if "меньше" in selected and "равен" in selected:
            op = " меньше либо равен "
        elif "меньше" in selected:
            op = " меньше "
        elif "больше" in selected and "равен" in selected:
            op = " больше либо равен "
        elif "больше" in selected:
            op = " больше "
        elif "равен" in selected and "не" not in selected:
            op = " равен "
        else:
            op = " не равен "

        # Левый операнд
        left_frame = ttk.Frame(frame)
        left_frame.pack(side="left")
        left_combo = ttk.Combobox(left_frame, style="SdCustomCombobox.TCombobox", values=["термины", "операции"], state="readonly")
        left_combo.pack()
        left_combo.operand_type = "left"  # Помечаем тип операнда
        left_combo.needs_logic_restore = True  # Для восстановления логики
        left_combo.bind("<<ComboboxSelected>>", 
                    lambda e: self.on_operand_selected(left_combo, left_frame, is_main_left=True))

        # Оператор
        ttk.Label(frame, text=op).pack(side="left")

        # Правый операнд
        right_frame = ttk.Frame(frame)
        right_frame.pack(side="left")
        right_combo = ttk.Combobox(right_frame, style="SdCustomCombobox.TCombobox", values=["термины", "значения", "операции"], state="readonly")
        right_combo.pack()
        right_combo.operand_type = "right"  # Помечаем тип операнда
        right_combo.needs_logic_restore = True  # Для восстановления логики
        right_combo.bind("<<ComboboxSelected>>", 
                        lambda e: self.on_operand_selected(right_combo, right_frame, is_main_left=False))

    def on_operand_selected(self, combo, parent_frame, is_main_left):
        """Обрабатывает выбор типа операнда (термины/значения/операции)"""
        selected = combo.get()
        combo.destroy()
        
        if selected == "термины":
            self.create_term_combobox(parent_frame, is_main_left)
        elif selected == "значения":
            self.create_value_entry(parent_frame)
        elif selected == "операции":
            self.create_operation_combobox(parent_frame, is_main_left)

    def create_term_combobox(self, parent_frame, is_main_left):
        """Создает комбобокс с терминами из БД"""
        # Создаем комбобокс
        cb_style = Style('minty')
        cb_style.configure("TermCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1, postoffset=(0, 0, 200, 0))
        cb = ttk.Combobox(parent_frame, style="TermCustomCombobox.TCombobox", state="readonly")
        cb.pack()
        
        # Помечаем для восстановления логики
        cb.operand_type = "left" if is_main_left else "right"
        cb.needs_logic_restore = True
        cb.role = "dimensional_term"
        
        # Устанавливаем логику обновления
        self.setup_dimensional_term_logic(cb)
        self.make_entry_autoresize(cb)

    def make_entry_autoresize(self, entry, min_chars=10, padding=2):
        def resize(event=None):
            content = entry.get()
            entry.config(width=max(len(content) + padding, min_chars))
        entry.bind('<KeyRelease>', resize)
        resize()

    def setup_dimensional_term_logic(self, combobox):
        """Устанавливает логику обновления для комбобокса размерных терминов"""
        def refresh_terms(event=None):
            # Проверяем существование виджета
            if not combobox.winfo_exists():
                return
                
            # Загружаем термины из БД
            terms = self.extractor.load_from_db("dimensional_terms", self.selected_subject, DimensionalExtractor())
            terms_list = [term["термин"] for term in terms]
            
            mapping_terms = self.extractor.load_from_db("mapping_terms", self.selected_subject, MappingExtractor())

            mapping_terms_list = [
                f"для значения понятия {mapping_term['Уточнение объема']['Область определения']}, " + mapping_term["термин"] for mapping_term in mapping_terms if mapping_term['Уточнение объема']['Область значений'] in ['множество вещественных чисел', 'множество целых чисел', 'множество названий']
                ]

            terms_list += mapping_terms_list

            # Обновляем значения
            current = combobox.get()
            combobox['values'] = terms_list
            combobox.set(current if current in terms_list else '')
        
        def on_combobox_select(event):
            self.make_entry_autoresize(combobox)
        # Привязываем обработчик
        combobox.bind("<Button-1>", refresh_terms)
        combobox.bind("<<ComboboxSelected>>", on_combobox_select)
        style = ttk.Style()
        style.layout('Wide.TCombobox', style.layout('TCombobox'))
        style.configure('Wide.TCombobox', borderwidth=0, padding=0, postoffset=(0, 0, 450, 0))
        combobox.configure(style='Wide.TCombobox')
        self.make_entry_autoresize(combobox)

        # Инициируем начальную загрузку
        refresh_terms()

    def create_value_entry(self, parent_frame):
        """Создает поле для ввода числового значения"""

        cb_style = Style('minty')
        cb_style.configure("SсCustomCombobox.TEntry",
                borderwidth=0,
                relief="flat",
                padding=1)
        
        entry = ttk.Entry(parent_frame, style="SсCustomCombobox.TEntry", font=TEXT_FONT)
        entry.pack()
        entry.config(validate="key", 
                    validatecommand=(parent_frame.register(self.validate_number), "%P"))

    @staticmethod
    def validate_number(value):
        if value == "" or value == "-":
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    def create_operation_combobox(self, parent_frame, is_main_left):
        """Создает комбобокс с операциями"""
        operations = [
            "Сумма \"левый терм\" и \"правый терм\"",
            "Разность \"левый терм\" и \"правый терм\"",
            "Произведение \"левый терм\" и \"правый терм\"",
            "Деление \"левый терм\" на \"правый терм\"",
            "Возведение \"левый терм\" в степень \"правый терм\""
        ]

        cb_style = Style('minty')
        cb_style.configure("SсCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1, postoffset=(0, 0, 210, 0))

        cb = ttk.Combobox(parent_frame, style="SсCustomCombobox.TCombobox", values=operations, state="readonly")
        cb.pack()
        
        # Помечаем для восстановления логики
        cb.operand_type = "left" if is_main_left else "right"
        cb.needs_logic_restore = True
        cb.role = "operation_selector"
        
        # Привязываем обработчик
        cb.bind("<<ComboboxSelected>>", 
                lambda e: self.create_operation_structure(cb, parent_frame, is_main_left))

    def create_operation_structure(self, combo, parent_frame, is_main_left):
        """Создает структуру для выбранной операции"""
        op_text = combo.get()
        combo.destroy()
        cb_style = Style('minty')
        cb_style.configure("onSetStandardCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1, postoffset=(0, 0, 100, 0))
        
        op_map = {
            "Сумма \"левый терм\" и \"правый терм\"": ("сумма", "и"),
            "Разность \"левый терм\" и \"правый терм\"": ("разность", "и"),
            "Произведение \"левый терм\" и \"правый терм\"": ("произведение", "и"),
            "Деление \"левый терм\" на \"правый терм\"": ("деление", "на"),
            "Возведение \"левый терм\" в степень \"правый терм\"": ("возведение", "в степень")
        }
        op_symbol = op_map.get(op_text, "?")
        
        op_frame = ttk.Frame(parent_frame)
        op_frame.pack()
        op_frame.formula_type = "dimensional_operation"  # Помечаем тип
        
        ttk.Label(op_frame, text="(").pack(side="left")

        inner_frame = ttk.Frame(op_frame)
        inner_frame.pack(side="left")
        ttk.Label(inner_frame, text=f"{op_symbol[0]} ").pack(side="left")

        # Левый операнд операции
        left_frame = ttk.Frame(inner_frame)
        left_frame.pack(side="left")
        left_combo = ttk.Combobox(left_frame, style="onSetStandardCustomCombobox.TCombobox",
                                values=["термины", "значения", "операции"], 
                                state="readonly")
        left_combo.pack()
        left_combo.operand_type = "left"
        left_combo.needs_logic_restore = True
        left_combo.bind("<<ComboboxSelected>>", 
                    lambda e: self.on_operand_selected(left_combo, left_frame, False))

        ttk.Label(inner_frame, text=f" {op_symbol[1]} ").pack(side="left")

        # Правый операнд операции
        right_frame = ttk.Frame(inner_frame)
        right_frame.pack(side="left")
        right_combo = ttk.Combobox(right_frame, style="onSetStandardCustomCombobox.TCombobox",
                                values=["термины", "значения", "операции"], 
                                state="readonly")
        right_combo.pack()
        right_combo.operand_type = "right"
        right_combo.needs_logic_restore = True
        right_combo.bind("<<ComboboxSelected>>", 
                        lambda e: self.on_operand_selected(right_combo, right_frame, False))

        ttk.Label(op_frame, text=")").pack(side="left")

    def insert_set_formula(self, parent_frame, combo):
        selected = combo.get()
        combo.destroy()

        frame = ttk.Frame(parent_frame)
        frame.pack()

        if "принадлежит" in selected and "не" not in selected:
            op = " принадлежит "
        elif "принадлежит" in selected and "не" in selected:
            op = " не принадлежит "
        elif "подмножеством либо равен" in selected:
            op = " является подмножеством либо равно "
        elif "подмножеством" in selected and "не" not in selected:
            op = " является подмножеством "
        elif "подмножеством" in selected and "не" in selected:
            op = " не является подмножеством "
        elif "равно" in selected and "не" not in selected:
            op = " равно "
        else:
            op = " не равно "

        left_frame = ttk.Frame(frame)
        left_frame.pack(side="left")
        cb_style = Style('minty')
        cb_style.configure("SeCustomCombobox.TCombobox",
            borderwidth=0,
            relief="flat",
            padding=1)
        if "левый терм" in selected:
            left_combo = ttk.Combobox(left_frame, style="SeCustomCombobox.TCombobox", values=["термины", "значения"], state="readonly")
            left_combo.pack()
            left_combo.bind("<<ComboboxSelected>>", 
                            lambda e: self.on_set_operand_selected(left_combo, left_frame, "element"))
        else:
            left_combo = ttk.Combobox(left_frame, style="SeCustomCombobox.TCombobox", values=["термины"], state="readonly")
            left_combo.pack()
            left_combo.bind("<<ComboboxSelected>>", 
                            lambda e: self.on_set_operand_selected(left_combo, left_frame, "set"))

        ttk.Label(frame, text=op).pack(side="left")

        if ("левое множество" in selected) and op in [' равно ', ' не равно ']:
            right_frame = ttk.Frame(frame)
            right_frame.pack(side="left")

            right_combo = ttk.Combobox(right_frame, style="SeCustomCombobox.TCombobox", values=["термины", "операции", "пустому множеству"], state="readonly")
            right_combo.pack()
            right_combo.bind("<<ComboboxSelected>>", 
                            lambda e: self.on_set_operand_selected(right_combo, right_frame, "set"))
        else:
            right_frame = ttk.Frame(frame)
            right_frame.pack(side="left")

            right_combo = ttk.Combobox(right_frame, style="SeCustomCombobox.TCombobox", values=["термины", "операции"], state="readonly")
            right_combo.pack()
            right_combo.bind("<<ComboboxSelected>>", 
                            lambda e: self.on_set_operand_selected(right_combo, right_frame, "set"))

    def on_set_operand_selected(self, combo, parent_frame, operand_type):
        """Обрабатывает выбор типа операнда для множественных формул"""
        selected = combo.get()
        combo.destroy()
        cb_style = Style('minty')
        cb_style.configure("SeCustomCombobox.TCombobox",
            borderwidth=0,
            relief="flat",
            padding=1)
        def create_empty_entry(parent_frame):
            """Создает поле для ввода числового значения"""
            entry = ttk.Entry(parent_frame, width=10)
            entry.pack()
            entry.insert(0, "пустому множеству")

        if selected == "термины":
            self.create_set_term_combobox(parent_frame, operand_type)
        elif selected == "значения":
            self.create_value_entry(parent_frame)
        elif selected == "пустому множеству":
            create_empty_entry(parent_frame)
        elif selected == "операции":
            set_operations = [
                "Объединение \"левое множество\" и \"правое множество\"",
                "Пересечение \"левое множество\" и \"правое множество\"",
                "Разность \"левое множество\" и \"правое множество\""
            ]
            cb = ttk.Combobox(parent_frame, style="SeCustomCombobox.TCombobox", values=set_operations, state="readonly")
            cb.pack()
            cb.bind("<<ComboboxSelected>>", 
                lambda e: self.create_set_operation_structure(cb, parent_frame))

    def create_set_operation_structure(self, combo, parent_frame):
        """Создает структуру для выбранной операции над множествами"""
        op_text = combo.get()
        combo.destroy()

        op_map = {
            "Объединение \"левое множество\" и \"правое множество\"": ("объединение", "и"),
            "Пересечение \"левое множество\" и \"правое множество\"": ("пересечение", "и"),
            "Разность \"левое множество\" и \"правое множество\"": ("разность", "и")
        }
        
        cb_style = Style('minty')
        cb_style.configure("SeCustomCombobox.TCombobox",
            borderwidth=0,
            relief="flat",
            padding=1)

        op_name, connector = op_map.get(op_text, ("?", "?"))
        
        op_frame = ttk.Frame(parent_frame)
        op_frame.pack()
        
        ttk.Label(op_frame, text="(").pack(side="left")
        
        inner_frame = ttk.Frame(op_frame)
        inner_frame.pack(side="left")
        
        ttk.Label(inner_frame, text=f"{op_name} ").pack(side="left")
        
        left_frame = ttk.Frame(inner_frame)
        left_frame.pack(side="left")
        left_combo = ttk.Combobox(left_frame, style="SeCustomCombobox.TCombobox",
                                values=["термины", "операции"], 
                                state="readonly")
        left_combo.pack()
        left_combo.bind("<<ComboboxSelected>>", 
                    lambda e: self.on_set_operand_selected(left_combo, left_frame, "set"))

        ttk.Label(inner_frame, text=f" {connector} ").pack(side="left")
        
        right_frame = ttk.Frame(inner_frame)
        right_frame.pack(side="left")
        right_combo = ttk.Combobox(right_frame, style="SeCustomCombobox.TCombobox",
                                values=["термины", "операции"], 
                                state="readonly")
        right_combo.pack()
        right_combo.bind("<<ComboboxSelected>>", 
                    lambda e: self.on_set_operand_selected(right_combo, right_frame, "set"))
        
        ttk.Label(op_frame, text=")").pack(side="left")

    def create_set_term_combobox(self, parent_frame, operand_type):
        """Создает комбобокс с терминами в зависимости от типа операнда"""
        if operand_type == "set":
            set_terms = self.extractor.load_from_db("set_terms", self.selected_subject, SetExtractor())
            term_names = [term["термин"] for term in set_terms]
        else:  
            scalar_terms = self.extractor.load_from_db("scalar_terms", self.selected_subject, ScalarExtractor())
            dimensional_terms = self.extractor.load_from_db("dimensional_terms", self.selected_subject, DimensionalExtractor())
            term_names = [term["термин"] for term in scalar_terms + dimensional_terms]
        cb_style = Style('minty')
        cb_style.configure("SeCustomCombobox.TCombobox",
            borderwidth=0,
            relief="flat",
            padding=1)
        cb = ttk.Combobox(parent_frame, style="SeCustomCombobox.TCombobox", values=term_names, state="readonly")
        cb.pack()

    def on_kernel_option_selected(self, parent_frame, combo):
        selected_text = combo.get()
        combo.destroy()

        elements = self.parse_template(selected_text)
        for el_type, content in elements:
            if el_type == "text":
                ttk.Label(parent_frame, text=content).pack(side="left")
            elif el_type == "placeholder":
                ph_frame = ttk.Frame(parent_frame)
                ph_frame.pack(side="left")
                self.create_placeholder_combobox(ph_frame)

    def parse_template(self, template_str):
        elements = []
        remaining = template_str
        markers = ["левая_формула", "правая_формула"]

        while remaining:
            positions = {marker: remaining.find(marker) for marker in markers}
            valid_positions = {k:v for k,v in positions.items() if v != -1}
            
            if not valid_positions:
                elements.append(("text", remaining))
                break

            next_marker = min(valid_positions, key=lambda k: valid_positions[k])
            pos = positions[next_marker]

            if pos > 0:
                elements.append(("text", remaining[:pos]))
            
            elements.append(("placeholder", next_marker))
            remaining = remaining[pos + len(next_marker):]

        return elements

    def create_placeholder_combobox(self, ph_frame):
        options = self.onto_template_options.copy()

        cb_style = Style('minty')
        cb_style.configure("insertStandarddCustomCombobox.TCombobox",
                borderwidth=0,
                relief="flat",
                padding=1, postoffset=(0, 0, 210, 0))

        combo = ttk.Combobox(ph_frame, style="insertStandarddCustomCombobox.TCombobox", values=options, state="readonly")
        combo.pack()
        combo.bind("<<ComboboxSelected>>", 
            lambda e: self.on_placeholder_selected(ph_frame, combo))

    def on_placeholder_selected(self, ph_frame, combo):
        selected = combo.get()
        combo.destroy()

        if selected == "Шаблоны формул ядра":
            self.insert_kernel_formula(ph_frame)
        elif selected == "Шаблоны формул стандартного расширения":
            self.insert_standard_formula(ph_frame)

class OntologyAgreementsTab(FormulaTab):
    def __init__(self, parent, selected_subject):
        self.parent = parent
        self.selected_subject = selected_subject
        self.onto_template_options = [
            "Шаблоны формул ядра",
            "Шаблоны формул стандартного расширения"
        ]
        self.extractor = TermExtractor(strategy=None)
        self.formula_extractor = FormulaExtractor(self.selected_subject)
        self.widget_id_map = {} 
        self.build_ui()

    def build_ui(self):
        for widget in self.parent.winfo_children():
            widget.destroy()
        onto_frame = ttk.LabelFrame(self.parent, text="Введите определения онтологических соглашений", padding=10)
        onto_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas_container = ttk.Frame(onto_frame)
        canvas_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(canvas_container, bg="#f4ffe9", highlightthickness=0)
        v_scroll = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(onto_frame, orient="horizontal", command=canvas.xview)

        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.template_container = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self.template_container, anchor="nw")

        def update_scrollbars(event=None):
            canvas.update_idletasks()
            if self.template_container.winfo_reqwidth() > canvas.winfo_width():
                h_scroll.pack(side="bottom", fill="x") if not h_scroll.winfo_ismapped() else None
            else:
                h_scroll.pack_forget() if h_scroll.winfo_ismapped() else None

        self.template_container.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            update_scrollbars()
        ))

        def show_template_menu(event):
            self.template_menu.tk_popup(event.x_root, event.y_root)

        btn_plus = tk.Button(onto_frame, text="+", font=("Arial", 16, "bold"),
                            fg="white", bg="#6abc4f", bd=0, relief="flat",
                            activebackground="#85d362", width=2, height=1)
        btn_plus.pack(anchor="w", pady=5, padx=5)
        btn_plus.bind("<Button-1>", show_template_menu)

        bottom_frame = ttk.Frame(self.parent)
        bottom_frame.pack(fill="x", side="bottom", pady=(10, 0), padx=10)
        extract_btn = ttk.Button(bottom_frame, text="Извлечь", command=self.extract_action)
        extract_btn.pack(side="right")
        self.load_ui('ontology')
        self.create_template_menu() 

    def create_template_menu(self):
        self.template_menu = tk.Menu(self.template_container, tearoff=0, bg="#f0ffe0", fg="black", font=TEXT_FONT)
        self.template_menu._menu_commands = {}

        for idx, option in enumerate(self.onto_template_options):
            command_name = f"template_option_{idx}"
            def make_command(opt=option):
                return lambda: self.handle_template_choice(opt)
            register_command(command_name, make_command())
            self.template_menu.add_command(label=option, command=command_registry[command_name])
            self.template_menu._menu_commands[idx] = command_name

    def handle_template_choice(self, template_name):
        new_row_frame = ttk.Frame(self.template_container)
        new_row_frame.pack(anchor="w", pady=5,  expand=True)

        def remove_template():
            new_row_frame.destroy()
        register_command(f"remove_template_{id(new_row_frame)}", remove_template)

        btn_remove = tk.Button(new_row_frame, text="X", 
                            command=command_registry[f"remove_template_{id(new_row_frame)}"],
                            font=("Arial", 8, "bold"), fg="white", bg="red", relief="flat")
        btn_remove._command_name = f"remove_template_{id(new_row_frame)}"
        btn_remove.pack(side="right", padx=(5, 0))

        if template_name == "Шаблоны формул ядра":
            self.insert_kernel_formula(new_row_frame)
        elif template_name == "Шаблоны формул стандартного расширения":
            self.insert_standard_formula(new_row_frame)

    def extract_action(self):
        # print("=== Извлечение онтологических соглашений ===")

        self.formula_extractor.serialize(self.template_container, 'ontology')

class KnowledgeTab(FormulaTab):

    def __init__(self, parent, selected_subject):
        self.parent = parent
        self.selected_subject = selected_subject
        self.onto_template_options = [
            "Шаблоны формул ядра",
            "Шаблоны формул стандартного расширения"
        ]
        self.extractor = TermExtractor(strategy=None)
        self.formula_extractor = FormulaExtractor(self.selected_subject)
        self.widget_id_map = {} 
        self.build_ui()

    def build_ui(self):
        for widget in self.parent.winfo_children():
            widget.destroy()
        onto_frame = ttk.LabelFrame(self.parent, text="Введите определения знаний", padding=10)
        onto_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas_container = ttk.Frame(onto_frame)
        canvas_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(canvas_container, bg="#f4ffe9", highlightthickness=0)
        v_scroll = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(onto_frame, orient="horizontal", command=canvas.xview)

        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.template_container = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self.template_container, anchor="nw")

        def update_scrollbars(event=None):
            canvas.update_idletasks()
            if self.template_container.winfo_reqwidth() > canvas.winfo_width():
                h_scroll.pack(side="bottom", fill="x") if not h_scroll.winfo_ismapped() else None
            else:
                h_scroll.pack_forget() if h_scroll.winfo_ismapped() else None

        self.template_container.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            update_scrollbars()
        ))

        btn_plus = tk.Button(onto_frame, text="+", font=("Arial", 16, "bold"),
                    fg="white", bg="#6abc4f", bd=0, relief="flat",
                    activebackground="#85d362", width=2, height=1)
        btn_plus.pack(anchor="nw", pady=5, padx=5)
        btn_plus.config(command=self.add_implication_kernel_template)

        bottom_frame = ttk.Frame(self.parent)
        bottom_frame.pack(fill="x", side="bottom", pady=(10, 0), padx=10)
        extract_btn = ttk.Button(bottom_frame, text="Извлечь", command=self.extract_action)
        extract_btn.pack(side="right")
        self.load_ui('knowledge')

    def add_implication_kernel_template(self):
        # Создаем новую строку для шаблона
        new_row_frame = ttk.Frame(self.template_container)
        new_row_frame.pack(pady=5, anchor="w")

        def remove_template():
            new_row_frame.destroy()
        register_command(f"remove_template_{id(new_row_frame)}", remove_template)

        btn_remove = tk.Button(new_row_frame, text="X", 
                            command=command_registry[f"remove_template_{id(new_row_frame)}"],
                            font=("Arial", 8, "bold"), fg="white", bg="red", relief="flat")
        btn_remove._command_name = f"remove_template_{id(new_row_frame)}"
        btn_remove.pack(side="right", padx=(5, 0))

        # Вставляем конкретный шаблон
        main_frame = ttk.Frame(new_row_frame)
        main_frame.pack(fill="x", anchor="w")

        ttk.Label(main_frame, text="(").pack(side="left")
        inner_frame = ttk.Frame(main_frame)
        inner_frame.pack(side="left", fill="x")
        ttk.Label(main_frame, text=")").pack(side="left")

        # Подставляем нужную формулу
        selected_text = "если левая_формула то правая_формула"
        elements = self.parse_template(selected_text)

        for el_type, content in elements:
            if el_type == "text":
                ttk.Label(inner_frame, text=content).pack(side="left")
            elif el_type == "placeholder":
                ph_frame = ttk.Frame(inner_frame)
                ph_frame.pack(side="left")
                self.create_placeholder_combobox(ph_frame)

    def extract_action(self):
        # print("=== Извлечение знаний ===")

        self.formula_extractor.serialize(self.template_container, 'knowledge')

class ModelBuildingTab:
    def __init__(self, parent, selected_subject):
        self.parent = parent
        self.selected_subject = selected_subject
        self.model_generator = ModelGenerator(self.selected_subject)
        self.build_ui()

    def build_ui(self):

        for widget in self.parent.winfo_children():
            widget.destroy()
        # Основной фрейм
        main_frame = ttk.Frame(self.parent)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Фрейм для вывода информации
        output_frame = ttk.LabelFrame(main_frame, text="Результат построения модели")
        output_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Текстовое поле с прокруткой для вывода JSON
        self.output_text = scrolledtext.ScrolledText(
            output_frame, 
            wrap=tk.WORD,
            font=('Consolas', 10),
            height=15
        )
        self.output_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.output_text.config(state=tk.DISABLED)  # Блокируем редактирование
        
        # Нижний фрейм с кнопкой
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=(5, 0))
        
        # Кнопка для построения модели
        build_btn = ttk.Button(
            bottom_frame, 
            text="Построить модель", 
            command=self.build_model
        )
        build_btn.pack(side="right")

    def build_model(self):
        # Очищаем предыдущий вывод
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        
        self.model_generator.build_concepts_model()
        self.model_generator.build_formula_model()

        try:
            # Загружаем данные из JSON-файла
            with open(f'{self.selected_subject}_model.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Форматируем вывод
            output = "=== ПОНЯТИЯ ===\n\n"
            for i, concept in enumerate(data["понятия"], 1):
                output += f"{i}. {concept}\n"
            
            output += "\n=== ОНТОЛОГИЧЕСКИЕ СОГЛАШЕНИЯ ===\n\n"
            if data["онтологические соглашения"]:
                for i, agreement in enumerate(data["онтологические соглашения"], 1):
                    output += f"{i}. {agreement}\n"
            else:
                output += "Пусто\n"
            
            output += "\n=== ЗНАНИЯ ===\n\n"
            if data["знания"]:
                for i, knowledge in enumerate(data["знания"], 1):
                    output += f"{i}. {knowledge}\n"
            else:
                output += "Пусто\n"
            
            # Вставляем отформатированный текст
            self.output_text.insert(tk.END, output)
            
        except FileNotFoundError:
            self.output_text.insert(tk.END, "Ошибка: Файл 'результат.json' не найден!")
        except json.JSONDecodeError:
            self.output_text.insert(tk.END, "Ошибка: Некорректный формат JSON-файла!")
        except Exception as e:
            self.output_text.insert(tk.END, f"Неизвестная ошибка: {str(e)}")
        
        # Блокируем редактирование
        self.output_text.config(state=tk.DISABLED)
        
        # print("Построение модели завершено")

class SubjectSelectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Выбор предметной области")
        # self.root.configure(bg=BG_COLOR)
        self.previous_tab_index = 0
        self.selected_subject = None
        self.buttons = {}
        
        self.template_options = [
            "Шаблон для скалярных величин",
            "Шаблон для размерных величин",
            "Шаблон для величин множеств",
            "Шаблон для величин отображений",
            "Шаблон для объединенных величин",
            "Шаблон для структурных величин",
            "Шаблон для величин последовательностей"
        ]
        
        self.create_widgets()
        self.render_subject_buttons()
        self.apply_custom_styles()

    def load_subject_areas_from_db(self):
        try:
            conn = sqlite3.connect("terms.db")
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS domains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE
                )
            ''')
            cursor.execute('SELECT name FROM domains ORDER BY name')
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке предметных областей: {str(e)}")
            return []

    def render_subject_buttons(self):
        # Очистим текущие кнопки
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.buttons.clear()

        subject_areas = self.load_subject_areas_from_db()

        for subject in subject_areas:
            btn = tb.Button(self.scrollable_frame, text=subject,
                            command=lambda s=subject: self.select_subject(s),
                            width=40)
            btn.pack(pady=4, anchor="center", padx=25)
            self.buttons[subject] = btn

            # Привязываем контекстное меню
            btn.bind("<Button-3>", lambda event, s=subject: self.show_context_menu(event, s))

    def show_context_menu(self, event, subject_name):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Удалить", command=lambda: self.delete_subject_area(subject_name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def delete_subject_area(self, subject_name):
        confirm = messagebox.askyesno("Подтверждение удаления",
                                    f"Вы уверены, что хотите удалить область: «{subject_name}»?")
        if not confirm:
            return
        try:
            conn = sqlite3.connect("terms.db")
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM domains WHERE name = ?", (subject_name,))
            conn.commit()
            conn.close()
            self.render_subject_buttons()
            if self.selected_subject == subject_name:
                self.selected_subject = None
                self.select_button["state"] = tk.DISABLED
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось удалить область: {str(e)}")

    def create_widgets(self):
        ttk.Label(self.root, text="Выберите предметную область:",
                   font=("Arial", 14, "bold")).pack(pady=(10, 5))

        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=10, pady=5)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.render_subject_buttons()

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10)

        self.select_button = ttk.Button(btn_frame, text="Выбрать предметную область",
                                        command=self.open_tabs_window, state=tk.DISABLED)
        self.select_button.grid(row=0, column=0, padx=5)

        self.create_button = ttk.Button(btn_frame, text="Создать", command=self.create_action)
        self.create_button.grid(row=0, column=1, padx=5)

    def select_subject(self, subject):
        self.selected_subject = subject
        self.select_button["state"] = tk.NORMAL

        for s, btn in self.buttons.items():
            btn.configure(style="Selected.TButton" if s == subject else "TButton")

    def open_tabs_window(self):
        if not self.selected_subject:
            return

        self.root.withdraw()
        self.tab_win = tb.Toplevel(self.root)
        self.tab_win.protocol("WM_DELETE_WINDOW", self.on_tabs_window_close)
        self.tab_win.title(f"Работа с предметной областью: {self.selected_subject}")
        self.tab_win.geometry("1250x500")

        window_width = 1250
        window_height = 500

        screen_width = self.tab_win.winfo_screenwidth()
        screen_height = self.tab_win.winfo_screenheight()

        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)-50

        self.tab_win.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

        self.notebook = ttk.Notebook(self.tab_win)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Создаем вкладки через отдельные классы
        tabs = {
            "Добавить понятия": ConceptsTab,
            "Добавить онтологические соглашения": OntologyAgreementsTab,
            "Добавить знания": KnowledgeTab,
            "Построить модель": ModelBuildingTab
        }

        self.tab_instances = {}

        for tab_name, tab_class in tabs.items():
            frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(frame, text=tab_name)
            
            # Создаем и сохраняем экземпляр вкладки
            if tab_name == "Добавить понятия":
                tab_instance = tab_class(frame, self.template_options, self.selected_subject)
            else:
                tab_instance = tab_class(frame, self.selected_subject)
                
            self.tab_instances[tab_name] = tab_instance

            self.notebook.bind("<ButtonPress-1>", self.on_tab_click)
            self.previous_tab_index = self.notebook.index("current")
    
    def on_tab_click(self, event):
        # Получаем индекс вкладки по координатам клика
        clicked_index = self.notebook.index(f"@{event.x},{event.y}")
        if clicked_index == self.previous_tab_index:
            return  # Клик на текущей вкладке — ничего не делаем

        prev_tab_name = self.notebook.tab(self.previous_tab_index, "text")
        next_tab_name = self.notebook.tab(clicked_index, "text")
        prev_tab_instance = self.tab_instances.get(prev_tab_name)

        if prev_tab_name == "Добавить понятия" and not prev_tab_instance.is_save:
            response = self.show_unsaved_changes_dialog(prev_tab_instance)

            if response == "save":
                if not prev_tab_instance.extract_action():
                    prev_tab_instance.is_save = False
                    return "break"  # Не переходим, т.к. валидация не прошла
                prev_tab_instance.is_save = True
            elif response == "discard":
                prev_tab_instance.is_save = True
            elif response == "cancel":
                return "break"

        # Даем системе завершить переход — но только теперь вручную
        self.notebook.select(clicked_index)

        # Обновляем UI новой вкладки, если нужно
        new_tab_instance = self.tab_instances.get(next_tab_name)
        if new_tab_instance and hasattr(new_tab_instance, 'build_ui'):
            new_tab_instance.build_ui()

        self.previous_tab_index = clicked_index
        return "break"  # Останавливаем дефолтное поведение — мы всё сделали вручную

    def show_unsaved_changes_dialog(self, tab_instance):
        dialog = tk.Toplevel(self.tab_win)
        dialog.title("Несохраненные изменения")
        dialog.transient(self.tab_win)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        window_width = 435
        window_height = 130

        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()

        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)

        dialog.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

        msg = "Введенные изменения не сохранены. Сохранить перед переходом?"
        label = ttk.Label(dialog, text=msg, padding=10)
        label.pack(padx=20, pady=10)
        
        response = None
        
        def set_response(r):
            nonlocal response
            response = r
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10, padx=20, fill=tk.X)
        
        ttk.Button(btn_frame, text="Сохранить", 
                command=lambda: set_response("save")).pack(side=tk.LEFT, expand=True)
        ttk.Button(btn_frame, text="Не сохранять", 
                command=lambda: set_response("discard")).pack(side=tk.LEFT, expand=True, padx=10)
        ttk.Button(btn_frame, text="Отмена", 
                command=lambda: set_response("cancel")).pack(side=tk.LEFT, expand=True)
        
        dialog.wait_window()
        return response

    def show_create_domain_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Новая предметная область")
        dialog.geometry("300x150")
        window_width = 300
        window_height = 150

        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()

        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)

        dialog.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

        dialog.grab_set()

        ttk.Label(dialog, text="Введите название новой предметной области:").pack(pady=(15, 5))
        
        name_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        entry.pack(pady=5)
        entry.focus()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        def cancel():
            dialog.destroy()

        def create():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Ошибка", "Название не может быть пустым.")
                return

            try:
                with sqlite3.connect("terms.db") as conn:
                    conn.execute("PRAGMA foreign_keys = ON")
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS domains (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE
                        )
                    ''')
                    cursor.execute('INSERT INTO domains (name) VALUES (?)', (name,))
                    conn.commit()
            except sqlite3.IntegrityError:
                messagebox.showerror("Ошибка", "Предметная область с таким названием уже существует.")
                return
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать область: {str(e)}")
                return

            dialog.destroy()
            self.render_subject_buttons()
            self.selected_subject = name
            self.open_tabs_window()

        ttk.Button(btn_frame, text="Создать", command=create).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=cancel).grid(row=0, column=1, padx=5)

    def on_tabs_window_close(self):
        self.tab_win.destroy()
        self.root.deiconify()

    def create_action(self):
        self.show_create_domain_dialog()

    def apply_custom_styles(self):
        style = tb.Style()
        style.theme_use(themename="minty")

        style.configure("TButton", font=("Arial", 12), padding=6)
        # style.map("TButton", background=[('active', '#cce8a0')])
        # style.configure("Selected.TButton", background="#d0f0b0", foreground="black")
        style.configure(".", background=BG_COLOR)
        style.configure("TNotebook", background=BG_COLOR, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[10, 5], font=("Arial", 12))
        # style.map("TNotebook.Tab", background=[("selected", "#d0f0b0"), ("active", "#d9f3a4")])