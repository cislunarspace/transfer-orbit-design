.. image:: _static/logo.png
   :align: center
   :width: 200

Transfer Orbit Design 文档
==========================

Transfer Orbit Design 是 `e2m2e <https://github.com/cislunarspace/e2m2e>`_ 的
GUI 前端：e2m2e 提供地月空间轨道设计所需的动力学模型与算法，本仓库把它们封装
成可视化桌面应用，通过"选工件 → 选操作 → 看结果"的三步交互完成轨道设计、
轨道族生成、轨道保持与稳定性分析。

.. toctree::
   :maxdepth: 2
   :caption: 入门

   narrative/readme
   guide/quickstart

.. toctree::
   :maxdepth: 2
   :caption: 使用指南

   guide/gui
   guide/tools
   guide/visualization
   guide/output
   guide/kernels

.. toctree::
   :maxdepth: 2
   :caption: 领域知识

   concepts/orbit-families
   concepts/ephemeris
   concepts/station-keeping

.. toctree::
   :maxdepth: 2
   :caption: 开发

   narrative/development
   dev/architecture
   dev/adr

索引
====

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
