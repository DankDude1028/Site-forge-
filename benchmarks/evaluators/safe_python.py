"""Small, bounded AST interpreter for coding tasks. Never calls eval/exec/compile.

This deliberately tests a useful restricted Python subset, not unrestricted Python.
All values originate in fixture data; no imports, filesystem, networking, classes,
reflection, decorators, dynamic function calls, recursion, or arbitrary attributes.
"""
from __future__ import annotations

import ast
import operator
from typing import Any, Callable


class UnsafeCode(ValueError):
    pass


class _Returned(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


BIN: dict[type, Callable[[Any, Any], Any]] = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
       ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
       ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
       ast.Is: operator.is_, ast.IsNot: operator.is_not}
BUILTINS: dict[str, Callable[..., Any]] = {"len": len, "sum": sum, "sorted": sorted, "abs": abs, "min": min,
            "max": max, "round": round, "str": str, "int": int, "float": float,
            "list": list, "dict": dict, "set": set, "tuple": tuple,
            "enumerate": lambda x: list(enumerate(x)), "zip": lambda *x: list(zip(*x)),
            "reversed": lambda x: list(reversed(x)), "all": all, "any": any}
METHODS: dict[type, set[str]] = {str: {"lower", "upper", "strip", "split", "join", "startswith", "endswith", "replace", "count", "isdigit", "capitalize"},
           list: {"append", "count", "index"}, dict: {"get", "items", "keys", "values"},
           set: {"add"}, tuple: {"count", "index"}}
NODES = {ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign,
         ast.AugAssign, ast.If, ast.For, ast.Expr, ast.Pass, ast.Break, ast.Continue,
         ast.Name, ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set,
         ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Subscript,
         ast.Slice, ast.Call, ast.Attribute, ast.keyword, ast.ListComp, ast.SetComp,
         ast.DictComp, ast.GeneratorExp, ast.comprehension, ast.Not, ast.USub, ast.UAdd,
         ast.And, ast.Or, *BIN, *CMP}


class SafePython:
    def __init__(self, code: str, *, operation_limit: int = 10000) -> None:
        if len(code) > 12000:
            raise UnsafeCode("Code exceeds limit")
        try:
            tree = ast.parse(code)
        except (SyntaxError, RecursionError) as error:
            raise UnsafeCode("Invalid Python syntax") from error
        nodes = list(ast.walk(tree))
        if len(nodes) > 1500 or any(type(node) not in NODES for node in nodes):
            raise UnsafeCode("Unsupported AST node")
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
            raise UnsafeCode("Exactly one solve(value) function is required")
        function = tree.body[0]
        if function.name != "solve" or function.decorator_list or function.returns or function.type_comment:
            raise UnsafeCode("Only undecorated solve(value) is allowed")
        args = function.args
        if len(args.args) != 1 or args.args[0].arg != "value" or args.args[0].annotation or args.defaults or args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
            raise UnsafeCode("Function must accept only value")
        for node in nodes:
            if isinstance(node, ast.Name) and (node.id.startswith("_") or node.id in {"eval", "exec", "open", "globals", "getattr", "__import__"}):
                raise UnsafeCode("Forbidden name")
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                raise UnsafeCode("Private attributes are forbidden")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id not in BUILTINS and node.func.id != "range":
                    raise UnsafeCode("Unknown function call")
                if not isinstance(node.func, (ast.Name, ast.Attribute)) or any(k.arg is None for k in node.keywords):
                    raise UnsafeCode("Dynamic calls are forbidden")
        self.function = function
        self.operation_limit = operation_limit
        self.remaining = operation_limit

    def guard(self, value: Any, depth: int = 0) -> Any:
        if depth > 20:
            raise UnsafeCode("Value nesting exceeds limit")
        if isinstance(value, (int, float)) and abs(value) > 1_000_000_000:
            raise UnsafeCode("Numeric magnitude exceeds limit")
        if isinstance(value, (str, list, tuple, set, dict)) and len(value) > 4096:
            raise UnsafeCode("Collection exceeds limit")
        if isinstance(value, dict):
            for k, v in value.items():
                self.guard(k, depth + 1)
                self.guard(v, depth + 1)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                self.guard(item, depth + 1)
        return value

    def tick(self) -> None:
        self.remaining -= 1
        if self.remaining <= 0:
            raise UnsafeCode("Operation budget exceeded")

    def solve(self, value: Any) -> Any:
        self.remaining = self.operation_limit
        env = {"value": self.guard(value)}
        try:
            self.block(self.function.body, env)
        except _Returned as result:
            return self.guard(result.value)
        return None

    def assign(self, target: ast.AST, value: Any, env: dict[str, Any]) -> None:
        self.guard(value)
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            if len(target.elts) != len(value):
                raise UnsafeCode("Unpack mismatch")
            for child, item in zip(target.elts, value):
                self.assign(child, item, env)
        elif isinstance(target, ast.Subscript):
            container = self.expression(target.value, env)
            key = self.expression(target.slice, env)
            container[key] = value
            self.guard(container)
        else:
            raise UnsafeCode("Invalid assignment target")

    def block(self, statements: list[ast.stmt], env: dict[str, Any]) -> None:
        for node in statements:
            self.tick()
            if isinstance(node, ast.Return):
                raise _Returned(self.expression(node.value, env) if node.value else None)
            if isinstance(node, ast.Assign):
                value = self.expression(node.value, env)
                for target in node.targets:
                    self.assign(target, value, env)
            elif isinstance(node, ast.AugAssign):
                self.assign(node.target, self.binary(type(node.op), self.expression(node.target, env), self.expression(node.value, env)), env)
            elif isinstance(node, ast.If):
                self.block(node.body if self.expression(node.test, env) else node.orelse, env)
            elif isinstance(node, ast.For):
                values = self.expression(node.iter, env)
                self.guard(values)
                for item in values:
                    self.tick()
                    self.assign(node.target, item, env)
                    self.block(node.body, env)
                self.block(node.orelse, env)
            elif isinstance(node, ast.Expr):
                self.expression(node.value, env)
            elif isinstance(node, ast.Pass):
                continue
            else:
                raise UnsafeCode("Unsupported statement")

    def binary(self, op: type, left: Any, right: Any) -> Any:
        if op is ast.Mult and isinstance(left, (str, list, tuple)) and isinstance(right, int) and len(left) * abs(right) > 4096:
            raise UnsafeCode("Multiplication exceeds collection limit")
        if op is ast.Mult and isinstance(right, (str, list, tuple)) and isinstance(left, int) and len(right) * abs(left) > 4096:
            raise UnsafeCode("Multiplication exceeds collection limit")
        return self.guard(BIN[op](left, right))

    def comprehension(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp, env: dict[str, Any]) -> Any:
        rows: list[Any] = []
        def visit(index: int, local: dict[str, Any]) -> None:
            self.tick()
            if index == len(node.generators):
                if isinstance(node, ast.DictComp):
                    rows.append((self.expression(node.key, local), self.expression(node.value, local)))
                else:
                    rows.append(self.expression(node.elt, local))
                self.guard(rows)
                return
            gen = node.generators[index]
            if gen.is_async:
                raise UnsafeCode("Async is unsupported")
            for value in self.expression(gen.iter, local):
                self.tick()
                child = dict(local)
                self.assign(gen.target, value, child)
                if all(self.expression(test, child) for test in gen.ifs):
                    visit(index + 1, child)
        visit(0, dict(env))
        return dict(rows) if isinstance(node, ast.DictComp) else set(rows) if isinstance(node, ast.SetComp) else rows

    def expression(self, node: ast.AST | None, env: dict[str, Any]) -> Any:
        self.tick()
        if isinstance(node, ast.Constant):
            return self.guard(node.value)
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise UnsafeCode("Unknown variable")
            return env[node.id]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [self.expression(item, env) for item in node.elts]
            return self.guard(tuple(values) if isinstance(node, ast.Tuple) else set(values) if isinstance(node, ast.Set) else values)
        if isinstance(node, ast.Dict):
            return self.guard({self.expression(k, env): self.expression(v, env) for k, v in zip(node.keys, node.values)})
        if isinstance(node, ast.BinOp):
            return self.binary(type(node.op), self.expression(node.left, env), self.expression(node.right, env))
        if isinstance(node, ast.UnaryOp):
            value = self.expression(node.operand, env)
            return self.guard(not value if isinstance(node.op, ast.Not) else -value if isinstance(node.op, ast.USub) else +value)
        if isinstance(node, ast.BoolOp):
            result = None
            for value in node.values:
                result = self.expression(value, env)
                if isinstance(node.op, ast.And) and not result or isinstance(node.op, ast.Or) and result:
                    break
            return result
        if isinstance(node, ast.Compare):
            left = self.expression(node.left, env)
            for op, expr in zip(node.ops, node.comparators):
                right = self.expression(expr, env)
                if not CMP[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return self.expression(node.body if self.expression(node.test, env) else node.orelse, env)
        if isinstance(node, ast.Subscript):
            return self.guard(self.expression(node.value, env)[self.expression(node.slice, env)])
        if isinstance(node, ast.Slice):
            return slice(*(self.expression(getattr(node, key), env) if getattr(node, key) else None for key in ("lower", "upper", "step")))
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return self.guard(self.comprehension(node, env))
        if isinstance(node, ast.Call):
            args = [self.expression(item, env) for item in node.args]
            kwargs = {item.arg: self.expression(item.value, env) for item in node.keywords if item.arg is not None}
            if isinstance(node.func, ast.Name):
                if node.func.id == "range":
                    value = range(*args)
                    if len(value) > 1024:
                        raise UnsafeCode("Range exceeds limit")
                    return list(value)
                return self.guard(BUILTINS[node.func.id](*args, **kwargs))
            if not isinstance(node.func, ast.Attribute):
                raise UnsafeCode("Dynamic calls are forbidden")
            owner = self.expression(node.func.value, env)
            method = node.func.attr
            if method not in METHODS.get(type(owner), set()):
                raise UnsafeCode("Unapproved method")
            result = getattr(owner, method)(*args, **kwargs)
            self.guard(owner)
            if method in {"items", "keys", "values"}:
                result = list(result)
            return self.guard(result)
        raise UnsafeCode("Unsupported expression")
