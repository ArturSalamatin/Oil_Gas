"""Плагин pytest (-p plan_patch_plugin): правка шага 1 плана DEBT-075 в памяти до сбора тестов."""
import plan_apply

plan_apply.patch_in_memory()
