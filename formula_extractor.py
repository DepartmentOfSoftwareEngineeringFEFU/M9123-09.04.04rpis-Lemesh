import json
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk, scrolledtext
import ttkbootstrap as tb
from ttkbootstrap.constants import *

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

def clean_pack_info(pack_info):
    if not pack_info:
        return None
    clean_info = {}
    for k, v in pack_info.items():
        if k == 'in':
            # не сохраняем ключ 'in' — он указывает на родителя
            continue
        if isinstance(v, tuple):
            clean_info[k] = list(v)
        elif isinstance(v, (str, int, float, bool)) or v is None:
            clean_info[k] = v
    return clean_info

class FormulaExtractor:
    def __init__(self, selected_subject):
        self.selected_subject = selected_subject
        self.onto_parts = []
        self.terms = []

    def reconstruct_ontology_line(self, widget, indent=0):
        if isinstance(widget, ttk.Label):
            self.onto_parts.append(widget.cget("text"))
        elif isinstance(widget, (ttk.Combobox, ttk.Entry)):
            self.onto_parts.append(widget.get())
            self.terms.append(widget.get())
            
        elif isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                self.reconstruct_ontology_line(child, indent + 2)
        else:
            print(f"{' ' * indent}Other widget: {widget}")

    def serialize(self, template_container, formula_type):
        self.onto_parts = []
        self.terms = []
        self.reconstruct_ontology_line(template_container)
        if '' in self.onto_parts:
            messagebox.showerror(
                        "Пропуски в определениях", 
                        "Перед извлечением необходимо заполнить все поля ввода"
                    )
            return
        
        onto_str = "".join(self.onto_parts)
        ontology_agreements_list = onto_str.split(')(')
        
        if len(ontology_agreements_list) > 1:
            for i in range(0, len(ontology_agreements_list)):
                if i == 0:
                    ontology_agreements_list[i] = ontology_agreements_list[i]+')'
                elif i != len(ontology_agreements_list)-1:
                    ontology_agreements_list[i] = '('+ontology_agreements_list[i]+')'
                else:
                    ontology_agreements_list[i] = '('+ontology_agreements_list[i]

        filename = f"struct_{formula_type}_{self.selected_subject}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(ontology_agreements_list, f, ensure_ascii=False, indent=2)

        filename = f"ui_state_{formula_type}_{self.selected_subject}.json"
        data = self.serialize_widget(template_container)

        preproc_terms = [i.replace('для значения понятия ', '') for i in self.terms if 'для значения понятия ' in i]
        preproc_terms = [i.replace(', ', ',') for i in preproc_terms if ', ' if i]
        self.terms = [i for i in self.terms if 'для значения понятия ' not in i]

        for p_term in preproc_terms:
            self.terms += p_term.split(',')
        if check_json_serializable(data):
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            with open(f'{self.selected_subject}_{formula_type}_list_terms.json', 'w', encoding="utf-8") as f:
                json.dump(self.terms, f, ensure_ascii=False, indent=2)
        else:
            # print("Структура содержит неподдерживаемые объекты.")
            pass
    
    def serialize_widget(self, widget):
        widget_type = widget.winfo_class()
        data = {
            "type": widget_type,
            "children": [],
            "layout": clean_pack_info(widget.pack_info()) if widget.winfo_manager() == "pack" else None
        }

        # Добавляем специальные атрибуты для восстановления логики
        if hasattr(widget, 'formula_type'):
            data['formula_type'] = widget.formula_type
            
        if hasattr(widget, 'role'):
            data['role'] = widget.role
            
        if hasattr(widget, 'depends_on'):
            # Записываем ID виджета, от которого зависит текущий
            if widget.depends_on:
                data['depends_on_id'] = id(widget.depends_on)
            else:
                data['depends_on_id'] = None

        # Стандартные свойства виджетов
        if isinstance(widget, ttk.Label):
            data["text"] = widget.cget("text")

        elif isinstance(widget, ttk.Combobox):
            values = widget["values"]
            if isinstance(values, tuple):
                values = list(values)
            data["values"] = values
            data["selected"] = widget.get()
            
            # Сохраняем специальные атрибуты
            if hasattr(widget, 'operand_type'):
                data['operand_type'] = widget.operand_type
            if hasattr(widget, 'role'):
                data['role'] = widget.role

        elif isinstance(widget, ttk.Entry):
            data["text"] = widget.get()

        elif isinstance(widget, tk.Button):
            data["text"] = widget.cget("text")
            data["command_name"] = getattr(widget, "_command_name", None)

        elif isinstance(widget, tk.Menu):
            data["menu_items"] = []
            for i in range(widget.index("end") + 1):
                item_type = widget.type(i)
                label = widget.entrycget(i, "label")
                cmd_name = getattr(widget, "_menu_commands", {}).get(i)
                item_data = {
                    "type": item_type,
                    "label": label,
                    "command_name": cmd_name
                }
                data["menu_items"].append(item_data)

        elif isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
            for child in widget.winfo_children():
                child_data = self.serialize_widget(child)
                if child_data:  # Добавляем только если получили данные
                    data["children"].append(child_data)

        return data