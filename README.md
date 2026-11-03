# svg-architecture-diagram 技能用户指南

当前发布版本见同目录的 [VERSION](./VERSION)。开始画图时，AI 应读取该文件，并显示版本、实际加载位置和当前阶段。

## 1. 技能做什么

你用自然语言描述要画的系统。技能指导 AI：

1. 先显示版本和本次实际加载的 `SKILL.md` 路径。
2. 从当前项目或你的描述里梳理层和模块，不套用固定产品。
3. 有对齐、等宽、别太细长、别太乱这类排版要求时，用自带脚本生成分层架构 SVG。
4. 把 SVG 写到当前项目（例如 `docs/` 或项目根目录），不写进技能目录。
5. 架构图只表达静态层次。要看调用或数据流时，另出一张链路图。

`svg-architecture-diagram` 是可分发的技能目录，不绑定单一 AI 客户端，也不绑定某种编程语言或业务领域。可安装到支持 Skills 的客户端（例如 Claude Code、Cursor 或 VS Code Copilot）。目录放好后，确认客户端已经发现技能。

你不需要自己运行脚本。技能依赖客户端提供文件访问、命令执行和写文件能力。需要本机已有 **Python 3**。技能不会替你安装 Python。PNG 导出和更准确的文字测宽是可选项，分别需要本机已有 `cairosvg` 和 `Pillow`；没有它们仍可生成 SVG。

## 2. 安装

将整个 `svg-architecture-diagram` 目录放到客户端支持的技能目录，必须保留 [SKILL.md](./SKILL.md) 与 [生成脚本](./scripts/gen_layered_svg.py) 的相对位置：

```text
<客户端支持的技能目录>\
  svg-architecture-diagram\
    VERSION
    SKILL.md
    README.md
    references\
      design-rules.md
    scripts\
      gen_layered_svg.py
    assets\
      example-spec.json
      example-layered-arch.svg
```

常见客户端的安装位置示例（以下使用 Windows 路径写法）：

| 客户端 | 个人级：跨项目使用 | 项目级：仅在该项目使用 |
| --- | --- | --- |
| Claude Code | `<用户目录>\.claude\skills\svg-architecture-diagram\SKILL.md` | `<项目目录>\.claude\skills\svg-architecture-diagram\SKILL.md` |
| Cursor | `<用户目录>\.cursor\skills\svg-architecture-diagram\SKILL.md` | `<项目目录>\.cursor\skills\svg-architecture-diagram\SKILL.md` |
| GitHub Copilot（VS Code） | `<用户目录>\.copilot\skills\svg-architecture-diagram\SKILL.md` | `<项目目录>\.github\skills\svg-architecture-diagram\SKILL.md` |

`<用户目录>` 和 `<项目目录>` 都是占位符。不要放进客户端自带的内部技能目录（例如 `.cursor\skills-cursor`）。跨业务项目使用优先选个人级安装。客户端版本和功能支持可能不同，安装后要确认技能已被发现。这些目录示例不代表已在所有客户端完成运行验收。

官方说明：[Claude Code](https://code.claude.com/docs/en/skills)、[Cursor](https://cursor.com/help/customization/skills)、[VS Code Copilot](https://code.visualstudio.com/docs/agent-customization/agent-skills)。

## 3. 脚本做什么

`scripts/gen_layered_svg.py` 读取一份 JSON，画出层等宽的分层架构 SVG。`--example` 打印同目录 `assets/example-spec.json`（一份与具体产品无关的订单服务示例）。脚本不生成链路图，也不安装依赖。
