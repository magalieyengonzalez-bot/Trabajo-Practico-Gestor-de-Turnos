#!/usr/bin/env python3
"""
turnos_peluqueria.py
Sistema de Turnos para Peluquería - Consola (POO, CSV <-> dict(JSON))
Requisitos:
 - Clases: Cliente, Turno, GestorTurnos
 - Persistencia: CSV + archivo dict (JSON) que actúa como "base de datos"
 - Menu interactivo en consola
 - Validaciones, filtros, manejo de excepciones
"""

import csv
import json
import os
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime

CSV_FILE = "turnos.csv"
DICT_FILE = "turnos_db.json"  # archivo que actúa como "dict" persistente
DATE_FORMAT = "%Y-%m-%d"      # formato para fechas
DATETIME_FORMAT = "%Y-%m-%d %H:%M"  # formato para turnos (fecha y hora)


@dataclass
class Cliente:
    dni: str
    nombre: str
    telefono: str = ""

    def to_dict(self):                # devuelve un diccionario con los campos del dataclass 
        return asdict(self)           # asdic recorre la instancia

    @staticmethod
    def from_dict(d):
        return Cliente(dni=d["dni"], nombre=d["nombre"], telefono=d.get("telefono", ""))  # recibe un diccionario d y devuelve una instacia cliente


@dataclass
class Turno:
    id: str
    cliente_dni: str     # no referencia como objeto para simpliciad de serialización
    datetime_str: str  # ISO-ish string in DATETIME_FORMAT  guarda fecha como string
    servicio: str
    estado: str = "activo"  # activo, cancelado, realizado
    notas: str = ""

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return Turno(
            id=d["id"],
            cliente_dni=d["cliente_dni"],
            datetime_str=d["datetime_str"],
            servicio=d["servicio"],
            estado=d.get("estado", "activo"),
            notas=d.get("notas", ""),
        )

    def datetime_obj(self):
        return datetime.strptime(self.datetime_str, DATETIME_FORMAT)  #parsea. permite comparaciones y ordenamiento numerico/temporales


class GestorTurnos:            #mantiene en memoria clientesy turnos. ofrece metodos para operar sobre ellos y persistirlo
    def __init__(self, csv_path=CSV_FILE, dict_path=DICT_FILE):
        self.csv_path = csv_path
        self.dict_path = dict_path
        # Estructura interna: dict de clientes {dni: Cliente}, dict de turnos {id: Turno}
        self.clientes = {}
        self.turnos = {}
        # carga inicial si existe CSV o JSON
        if os.path.exists(self.dict_path):      # si existe el json lo carga
            try:
                self.load_from_dict()          #carga desde json
                # ensure CSV is in sync
                self.dump_to_csv()    #csv sincronizado con json
            except Exception as e:  
                print(f"[WARN] Error cargando dict ({self.dict_path}): {e}")
        elif os.path.exists(self.csv_path):  # manejar errores y notificar con print
            try:
                self.load_from_csv()
                self.dump_to_dict()
            except Exception as e:
                print(f"[WARN] Error cargando CSV ({self.csv_path}): {e}")

    # ---------- Persistencia ----------
    def dump_to_csv(self):           
        """Volcar turnos + clientes a CSV (cada fila: turno + cliente)"""
        fieldnames = [    
            "turno_id", "cliente_dni", "cliente_nombre", "cliente_telefono",
            "datetime_str", "servicio", "estado", "notas"    #cabecera del cvs
        ]
        try:
            with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:    #abre el archivo en modo escritura, evita el doble salto y soprta caracteres ASCII
                writer = csv.DictWriter(f, fieldnames=fieldnames)    #crea objetos que escsribe diccionarios como filas
                writer.writeheader()     #escribe la fila de cabeceras
                for t in self.turnos.values():          # itera por todos los objetos Turnos en memoria
                    cli = self.clientes.get(t.cliente_dni)     #obtiene el cliente asociado
                    writer.writerow({
                        "turno_id": t.id,
                        "cliente_dni": t.cliente_dni,
                        "cliente_nombre": cli.nombre if cli else "",
                        "cliente_telefono": cli.telefono if cli else "",
                        "datetime_str": t.datetime_str,
                        "servicio": t.servicio,
                        "estado": t.estado,
                        "notas": t.notas,     
                    })    #crea diccionario con las claves
        except Exception as e:     #caputura cualquier error de E/S lo imprime y relanza la excepcion
            print(f"[ERROR] No se pudo guardar CSV: {e}")
            raise #excepcion, para que llamador sepa
        # también guardar dict
        self.dump_to_dict()

    def load_from_csv(self):         # si no existe el csv no hace nada
        """Cargar desde CSV - construye clientes y turnos"""
        if not os.path.exists(self.csv_path):
            return
        with open(self.csv_path, mode="r", encoding="utf-8") as f: #abre el archivo en modo lectura
            reader = csv.DictReader(f)     # crea iterador que devuelve cada fila como diccionario
            self.clientes.clear()              #limpia los adtos actuales en memoria para cargar desdde csv
            self.turnos.clear()
            for row in reader:   #itera cada fila
                dni = row["cliente_dni"].strip()      #toma el campo y aplica strio() para quitar espacios de los extremos
                if dni:
                    # si cliente no existe, crearlo
                    if dni not in self.clientes:
                        self.clientes[dni] = Cliente(dni=dni, nombre=row.get("cliente_nombre", "").strip(), telefono=row.get("cliente_telefono", "").strip())
                # crear turno
                t = Turno(
                    id=row["turno_id"],
                    cliente_dni=dni,
                    datetime_str=row["datetime_str"],
                    servicio=row.get("servicio", ""),
                    estado=row.get("estado", "activo"),
                    notas=row.get("notas", ""),
                )
                self.turnos[t.id] = t

    def dump_to_dict(self):      #construye diccionario con dos claves clientes y turnos
        """Volcar dict a archivo JSON"""
        data = {
            "clientes": {dni: cli.to_dict() for dni, cli in self.clientes.items()},      #convierte cada cliente en un dict
            "turnos": {tid: t.to_dict() for tid, t in self.turnos.items()},               #mapea tid → t.to_dict()
        }
        with open(self.dict_path, "w", encoding="utf-8") as f:         #abre json para escritura
            json.dump(data, f, indent=2, ensure_ascii=False)     #escribe JSON formateado con indentación (legible), y ensure_ascii=False para mantener caracteres especiales (acentos) en UTF-8

    def load_from_dict(self):
        """Cargar desde archivo JSON (dict)"""
        with open(self.dict_path, "r", encoding="utf-8") as f: #abre json para lectura
            data = json.load(f)       # parsea el json a estructuras python (diccionario y listas). obtiene el subdiccionario de cliente o {} si no existe evita KeyError
        self.clientes = {dni: Cliente.from_dict(cd) for dni, cd in data.get("clientes", {}).items()}    # para devolver objetos 
        self.turnos = {tid: Turno.from_dict(td) for tid, td in data.get("turnos", {}).items()}

    # ---------- Operaciones ----------
    def registrar_cliente(self, dni, nombre, telefono=""):
        dni = dni.strip() # quita espacios 
        if dni in self.clientes:
            raise ValueError(f"Cliente con DNI {dni} ya registrado.") # si el dni ya existe lanza error
        cliente = Cliente(dni=dni, nombre=nombre.strip(), telefono=telefono.strip()) #crea instancia cliente
        self.clientes[dni] = cliente
        self.dump_to_dict()
        # no forzamos CSV aquí: turnos no cambiaron, pero se puede guardar si querés
        return cliente # retorna la instancia guardada

    def solicitar_turno(self, cliente_dni, datetime_str, servicio, notas=""):
        # valida cliente
        if cliente_dni not in self.clientes:
            raise ValueError("Cliente no registrado. Registre primero el cliente.")
        # parsea fecha/hora
        try:
            dt = datetime.strptime(datetime_str, DATETIME_FORMAT)
        except ValueError:
            raise ValueError(f"Formato de fecha/hora inválido. Use: {DATETIME_FORMAT}")
        # valida que no exista otro turno activo en mismo horario
        for t in self.turnos.values():
            if t.estado == "activo" and t.datetime_str == dt.strftime(DATETIME_FORMAT):
                raise ValueError("Ya existe un turno activo en ese horario.")
        # crear turno
        turno_id = str(uuid.uuid4())
        t = Turno(id=turno_id, cliente_dni=cliente_dni, datetime_str=dt.strftime(DATETIME_FORMAT), servicio=servicio.strip(), notas=notas.strip())
        self.turnos[turno_id] = t
        # volcar a dict y CSV
        self.dump_to_dict()
        self.dump_to_csv()
        return t

    def listar_turnos(self, filtro_cliente_dni=None, filtro_fecha=None, estado=None):
        """
        filtro_fecha: string 'YYYY-MM-DD' -> retorna turnos en esa fecha
        estado: None or "activo"/"cancelado"/"realizado"
        """
        results = []
        for t in self.turnos.values():
            if estado and t.estado != estado:
                continue
            if filtro_cliente_dni and t.cliente_dni != filtro_cliente_dni:
                continue
            if filtro_fecha:
                # comparar solo fecha parte de datetime_str
                try:
                    d = datetime.strptime(filtro_fecha, DATE_FORMAT).date()
                except ValueError:
                    raise ValueError(f"Formato de fecha inválido. Use: {DATE_FORMAT}")
                if t.datetime_obj().date() != d:
                    continue
            results.append(t)
        # ordenar por fecha/hora asc
        results.sort(key=lambda x: x.datetime_obj())
        return results

    def modificar_turno(self, turno_id, nuevo_datetime_str=None, nuevo_servicio=None, nuevas_notas=None):
        if turno_id not in self.turnos:
            raise KeyError("Turno no encontrado.")
        t = self.turnos[turno_id]
        if nuevo_datetime_str:
            try:
                dt = datetime.strptime(nuevo_datetime_str, DATETIME_FORMAT)
            except ValueError:
                raise ValueError(f"Formato de fecha/hora inválido. Use: {DATETIME_FORMAT}")
            # validar duplicado (excluyendo el mismo turno)
            for other in self.turnos.values():
                if other.id != t.id and other.estado == "activo" and other.datetime_str == dt.strftime(DATETIME_FORMAT):
                    raise ValueError("No se puede mover: ya existe otro turno activo en ese horario.")
            t.datetime_str = dt.strftime(DATETIME_FORMAT)
        if nuevo_servicio is not None:
            t.servicio = nuevo_servicio.strip()
        if nuevas_notas is not None:
            t.notas = nuevas_notas.strip()
        # guardar
        self.dump_to_dict()
        self.dump_to_csv()
        return t

    def cancelar_turno(self, turno_id):
        if turno_id not in self.turnos:
            raise KeyError("Turno no encontrado.")
        t = self.turnos[turno_id]
        t.estado = "cancelado"
        self.dump_to_dict()
        self.dump_to_csv()
        return t

    def marcar_realizado(self, turno_id):
        if turno_id not in self.turnos:
            raise KeyError("Turno no encontrado.")
        t = self.turnos[turno_id]
        t.estado = "realizado"
        self.dump_to_dict()
        self.dump_to_csv()
        return t

    # utilidades
    def buscar_cliente_por_nombre(self, nombre_parcial):
        nombre_parcial = nombre_parcial.lower().strip()
        return [c for c in self.clientes.values() if nombre_parcial in c.nombre.lower()]

    def exportar_csv_personalizado(self, path):
        old = self.csv_path
        self.csv_path = path
        self.dump_to_csv()
        self.csv_path = old


# ---------- Interfaz de consola ----------
def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


def pausa():
    input("\nEnter para continuar...")


def imprimir_turnos(lista, gestor: GestorTurnos):
    if not lista:
        print("-> No hay turnos que mostrar.")
        return
    print(f"{'ID':36}  {'DNI':10}  {'Nombre':20}  {'Fecha y Hora':16}  {'Servicio':15}  {'Estado':8}")
    print("-" * 110)
    for t in lista:
        cli = gestor.clientes.get(t.cliente_dni)
        nombre = cli.nombre if cli else "(sin cliente)"
        print(f"{t.id:36}  {t.cliente_dni:10}  {nombre[:20]:20}  {t.datetime_str:16}  {t.servicio[:15]:15}  {t.estado:8}")


def main_menu():
    gestor = GestorTurnos()
    while True:
        clear_console()
        print("=== SISTEMA DE TURNOS - PELUQUERÍA ===")
        print("1) Registrar nuevo cliente")
        print("2) Solicitar turno")
        print("3) Listar turnos")
        print("4) Modificar turno")
        print("5) Cancelar turno")
        print("6) Marcar turno como realizado")
        print("7) Guardar datos (CSV / dict)")
        print("8) Cargar datos desde CSV")
        print("9) Filtrar turnos por cliente o fecha")
        print("10) Exportar CSV personalizado")
        print("0) Salir")
        try:
            opt = input("Elegí una opción: ").strip()
            if opt == "1":
                dni = input("DNI: ").strip()
                nombre = input("Nombre y apellido: ").strip()
                tel = input("Teléfono (opcional): ").strip()
                try:
                    cliente = gestor.registrar_cliente(dni, nombre, tel)
                    print(f"Cliente registrado: {cliente}")
                except Exception as e:
                    print(f"[ERROR] {e}")
                pausa()
            elif opt == "2":
                dni = input("DNI del cliente: ").strip()
                if dni not in gestor.clientes:
                    print("Cliente no registrado.")
                    buscar = input("Desea buscar por nombre? (s/n): ").strip().lower()
                    if buscar == "s":
                        nombre_par = input("Ingrese parte del nombre: ").strip()
                        res = gestor.buscar_cliente_por_nombre(nombre_par)
                        if res:
                            print("Clientes encontrados:")
                            for c in res:
                                print(f"- {c.dni} | {c.nombre} | {c.telefono}")
                        else:
                            print("No se encontraron clientes.")
                    pausa()
                    continue
                fecha_hora = input(f"Ingrese fecha y hora ({DATETIME_FORMAT}): ").strip()
                servicio = input("Servicio solicitado: ").strip()
                notas = input("Notas (opcional): ").strip()
                try:
                    t = gestor.solicitar_turno(dni, fecha_hora, servicio, notas)
                    print("Turno creado con ID:", t.id)
                except Exception as e:
                    print(f"[ERROR] {e}")
                pausa()
            elif opt == "3":
                try:
                    lista = gestor.listar_turnos()
                    imprimir_turnos(lista, gestor)
                except Exception as e:
                    print(f"[ERROR] {e}")
                pausa()
            elif opt == "4":
                turno_id = input("ID del turno a modificar: ").strip()
                print("Dejar en blanco para no cambiar un campo.")
                nuevo_dt = input(f"Nuevo fecha y hora ({DATETIME_FORMAT}): ").strip()
                nuevo_serv = input("Nuevo servicio: ").strip()
                nuevas_notas = input("Nuevas notas: ").strip()
                try:
                    t = gestor.modificar_turno(
                        turno_id,
                        nuevo_datetime_str=(nuevo_dt if nuevo_dt else None),
                        nuevo_servicio=(nuevo_serv if nuevo_serv else None),
                        nuevas_notas=(nuevas_notas if nuevas_notas else None),
                    )
                    print("Turno modificado:", t)
                except Exception as e:
                    print(f"[ERROR] {e}")
                pausa()
            elif opt == "5":
                turno_id = input("ID del turno a cancelar: ").strip()
                try:
                    gestor.cancelar_turno(turno_id)
                    print("Turno cancelado.")
                except Exception as e:
                    print(f"[ERROR] {e}")
                pausa()
            elif opt == "6":
                turno_id = input("ID del turno a marcar como realizado: ").strip()
                try:
                    gestor.marcar_realizado(turno_id)
                    print("Turno marcado como realizado.")
                except Exception as e:
                    print(f"[ERROR] {e}")
                pausa()
            elif opt == "7":
                try:
                    gestor.dump_to_dict()
                    gestor.dump_to_csv()
                    print("Datos guardados correctamente.")
                except Exception as e:
                    print(f"[ERROR] {e}")
                pausa()
            elif opt == "8":
                # recargar CSV (si existe)
                if not os.path.exists(gestor.csv_path):
                    print("No existe el archivo CSV actual:", gestor.csv_path)
                else:
                    try:
                        gestor.load_from_csv()
                        gestor.dump_to_dict()
                        print("Datos cargados desde CSV.")
                    except Exception as e:
                        print(f"[ERROR] {e}")
                pausa()
            elif opt == "9":
                sub = input("Filtrar por (1) Cliente DNI, (2) Fecha (YYYY-MM-DD), (3) Estado: ").strip()
                if sub == "1":
                    dni = input("DNI: ").strip()
                    try:
                        lista = gestor.listar_turnos(filtro_cliente_dni=dni)
                        imprimir_turnos(lista, gestor)
                    except Exception as e:
                        print(f"[ERROR] {e}")
                elif sub == "2":
                    fecha = input(f"Fecha ({DATE_FORMAT}): ").strip()
                    try:
                        lista = gestor.listar_turnos(filtro_fecha=fecha)
                        imprimir_turnos(lista, gestor)
                    except Exception as e:
                        print(f"[ERROR] {e}")
                elif sub == "3":
                    est = input("Estado (activo / cancelado / realizado): ").strip()
                    try:
                        lista = gestor.listar_turnos(estado=est)
                        imprimir_turnos(lista, gestor)
                    except Exception as e:
                        print(f"[ERROR] {e}")
                else:
                    print("Opción inválida.")
                pausa()
            elif opt == "10":
                path = input("Ruta/Nombre archivo CSV a exportar (ej: copia_turnos.csv): ").strip()
                try:
                    gestor.exportar_csv_personalizado(path)
                    print("Exportado exitosamente a", path)
                except Exception as e:
                    print(f"[ERROR] {e}")
                pausa()
            elif opt == "0":
                print("Saliendo. Guardando datos...")
                gestor.dump_to_dict()
                gestor.dump_to_csv()
                print("Listo. Adiós.")
                break
            else:
                print("Opción inválida.")
                pausa()
        except KeyboardInterrupt:
            print("\nInterrumpido por usuario. Guardando y saliendo...")
            gestor.dump_to_dict()
            gestor.dump_to_csv()
            sys.exit(0)


if __name__ == "__main__":
    try:
        main_menu()
    except Exception as e:
        print(f"[FATAL] {e}")

        raise

