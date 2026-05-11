"""
TradingAgents GUI - Tkinter 图形界面
支持配置 LLM、交易参数，保存/加载 config.json，运行分析。
"""
import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from datetime import datetime, timedelta

CONFIG_FILE = "config.json"

DEFAULT_GUI_CONFIG = {
    "llm_provider": "openai",
    "api_key": "sk-2f4919d60a39866f769cd80971f760b35653904355614b89a6808addc7ee731c",
    "backend_url": "https://hcat.shop/v1",
    "deep_think_llm": "gpt-4o",
    "quick_think_llm": "gpt-4o-mini",
    "blockbeats_api_key": "bbp_18304449bb2a25e3bf96112e90ecec409c51aadc4bc8ad6f8f05f0f45676",
    "ticker": "BTC-USD",
    "trade_date": datetime.now().strftime("%Y-%m-%d"),
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "output_language": "Chinese",
    "selected_analysts": ["market", "social", "news", "fundamentals"],
}

PROVIDER_OPTIONS = ["openai", "deepseek", "qwen", "glm", "xai", "anthropic", "google", "openrouter", "ollama"]

ANALYST_OPTIONS = [
    ("market", "市场分析师 (技术面)"),
    ("fundamentals", "基本面分析师"),
    ("news", "新闻分析师"),
    ("social", "社交媒体分析师"),
]

LANGUAGE_OPTIONS = ["Chinese", "English", "Japanese", "Korean"]


class TradingAgentsGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TradingAgents - 加密货币 & 股票分析")
        self.root.geometry("820x720")
        self.root.resizable(True, True)

        self.config = DEFAULT_GUI_CONFIG.copy()
        self.running = False

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === LLM Configuration ===
        llm_frame = ttk.LabelFrame(main_frame, text="LLM 配置", padding=8)
        llm_frame.pack(fill=tk.X, pady=(0, 8))

        # Row 1: Provider + API Key
        row1 = ttk.Frame(llm_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="Provider:").pack(side=tk.LEFT)
        self.provider_var = tk.StringVar(value=self.config["llm_provider"])
        provider_cb = ttk.Combobox(row1, textvariable=self.provider_var, values=PROVIDER_OPTIONS, width=12, state="readonly")
        provider_cb.pack(side=tk.LEFT, padx=(4, 16))

        ttk.Label(row1, text="API Key:").pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=self.config["api_key"])
        api_key_entry = ttk.Entry(row1, textvariable=self.api_key_var, width=52, show="*")
        api_key_entry.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)

        # Toggle show/hide key
        self.show_key_var = tk.BooleanVar(value=False)
        def toggle_key():
            api_key_entry.config(show="" if self.show_key_var.get() else "*")
        ttk.Checkbutton(row1, text="显示", variable=self.show_key_var, command=toggle_key).pack(side=tk.LEFT)

        # Row 2: Base URL
        row2 = ttk.Frame(llm_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text="中转站 URL:").pack(side=tk.LEFT)
        self.backend_url_var = tk.StringVar(value=self.config["backend_url"])
        ttk.Entry(row2, textvariable=self.backend_url_var, width=60).pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        ttk.Button(row2, text="测试连接", command=self._test_relay).pack(side=tk.LEFT, padx=4)
        ttk.Label(row2, text="(留空则使用官方地址)", foreground="gray").pack(side=tk.LEFT)

        # Row 3: Models
        row3 = ttk.Frame(llm_frame)
        row3.pack(fill=tk.X, pady=2)

        ttk.Label(row3, text="深度思考模型:").pack(side=tk.LEFT)
        self.deep_model_var = tk.StringVar(value=self.config["deep_think_llm"])
        ttk.Entry(row3, textvariable=self.deep_model_var, width=20).pack(side=tk.LEFT, padx=(4, 16))

        ttk.Label(row3, text="快速思考模型:").pack(side=tk.LEFT)
        self.quick_model_var = tk.StringVar(value=self.config["quick_think_llm"])
        ttk.Entry(row3, textvariable=self.quick_model_var, width=20).pack(side=tk.LEFT, padx=4)

        # Row 4: BlockBeats API Key
        row4 = ttk.Frame(llm_frame)
        row4.pack(fill=tk.X, pady=2)

        ttk.Label(row4, text="BlockBeats Key:").pack(side=tk.LEFT)
        self.blockbeats_key_var = tk.StringVar(value=self.config.get("blockbeats_api_key", ""))
        ttk.Entry(row4, textvariable=self.blockbeats_key_var, width=52, show="*").pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        ttk.Label(row4, text="(加密新闻数据源，留空则用 CoinGecko)", foreground="gray").pack(side=tk.LEFT)

        # === Trading Parameters ===
        trade_frame = ttk.LabelFrame(main_frame, text="交易参数", padding=8)
        trade_frame.pack(fill=tk.X, pady=(0, 8))

        # Row 1: Ticker + Date
        trow1 = ttk.Frame(trade_frame)
        trow1.pack(fill=tk.X, pady=2)

        ttk.Label(trow1, text="分析标的:").pack(side=tk.LEFT)
        self.ticker_var = tk.StringVar(value=self.config["ticker"])
        ttk.Entry(trow1, textvariable=self.ticker_var, width=14).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(trow1, text="(股票: AAPL, 加密: BTC-USD)", foreground="gray").pack(side=tk.LEFT, padx=(0, 16))

        ttk.Label(trow1, text="交易日期:").pack(side=tk.LEFT)
        self.date_var = tk.StringVar(value=self.config["trade_date"])
        ttk.Entry(trow1, textvariable=self.date_var, width=12).pack(side=tk.LEFT, padx=4)

        # Row 2: Rounds + Language
        trow2 = ttk.Frame(trade_frame)
        trow2.pack(fill=tk.X, pady=2)

        ttk.Label(trow2, text="辩论轮数:").pack(side=tk.LEFT)
        self.debate_rounds_var = tk.IntVar(value=self.config["max_debate_rounds"])
        ttk.Spinbox(trow2, from_=1, to=5, textvariable=self.debate_rounds_var, width=4).pack(side=tk.LEFT, padx=(4, 16))

        ttk.Label(trow2, text="风控轮数:").pack(side=tk.LEFT)
        self.risk_rounds_var = tk.IntVar(value=self.config["max_risk_discuss_rounds"])
        ttk.Spinbox(trow2, from_=1, to=5, textvariable=self.risk_rounds_var, width=4).pack(side=tk.LEFT, padx=(4, 16))

        ttk.Label(trow2, text="输出语言:").pack(side=tk.LEFT)
        self.language_var = tk.StringVar(value=self.config["output_language"])
        ttk.Combobox(trow2, textvariable=self.language_var, values=LANGUAGE_OPTIONS, width=10, state="readonly").pack(side=tk.LEFT, padx=4)

        # Row 3: Analyst selection
        trow3 = ttk.Frame(trade_frame)
        trow3.pack(fill=tk.X, pady=2)

        ttk.Label(trow3, text="启用分析师:").pack(side=tk.LEFT)
        self.analyst_vars = {}
        for key, label in ANALYST_OPTIONS:
            var = tk.BooleanVar(value=key in self.config["selected_analysts"])
            self.analyst_vars[key] = var
            ttk.Checkbutton(trow3, text=label, variable=var).pack(side=tk.LEFT, padx=6)

        # === Buttons ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(btn_frame, text="保存配置", command=self._save_config).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="加载配置", command=self._load_config_dialog).pack(side=tk.LEFT, padx=4)

        self.run_btn = ttk.Button(btn_frame, text="▶ 开始分析", command=self._run_analysis)
        self.run_btn.pack(side=tk.RIGHT, padx=4)

        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止", command=self._stop_analysis, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT, padx=4)

        # Status label
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(btn_frame, textvariable=self.status_var, foreground="blue").pack(side=tk.RIGHT, padx=16)

        # === Output ===
        output_frame = ttk.LabelFrame(main_frame, text="运行输出", padding=4)
        output_frame.pack(fill=tk.BOTH, expand=True)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, font=("Consolas", 9))
        self.output_text.pack(fill=tk.BOTH, expand=True)

    def _get_current_config(self) -> dict:
        """Gather current GUI values into a config dict."""
        selected = [k for k, v in self.analyst_vars.items() if v.get()]
        return {
            "llm_provider": self.provider_var.get(),
            "api_key": self.api_key_var.get().strip(),
            "backend_url": self.backend_url_var.get().strip(),
            "deep_think_llm": self.deep_model_var.get().strip(),
            "quick_think_llm": self.quick_model_var.get().strip(),
            "blockbeats_api_key": self.blockbeats_key_var.get().strip(),
            "ticker": self.ticker_var.get().strip(),
            "trade_date": self.date_var.get().strip(),
            "max_debate_rounds": self.debate_rounds_var.get(),
            "max_risk_discuss_rounds": self.risk_rounds_var.get(),
            "output_language": self.language_var.get(),
            "selected_analysts": selected,
        }

    def _apply_config(self, cfg: dict):
        """Apply config dict to GUI widgets."""
        self.provider_var.set(cfg.get("llm_provider", "openai"))
        self.api_key_var.set(cfg.get("api_key", ""))
        self.backend_url_var.set(cfg.get("backend_url", ""))
        self.deep_model_var.set(cfg.get("deep_think_llm", "gpt-4o"))
        self.quick_model_var.set(cfg.get("quick_think_llm", "gpt-4o-mini"))
        self.blockbeats_key_var.set(cfg.get("blockbeats_api_key", ""))
        self.ticker_var.set(cfg.get("ticker", "BTC-USD"))
        self.date_var.set(cfg.get("trade_date", datetime.now().strftime("%Y-%m-%d")))
        self.debate_rounds_var.set(cfg.get("max_debate_rounds", 1))
        self.risk_rounds_var.set(cfg.get("max_risk_discuss_rounds", 1))
        self.language_var.set(cfg.get("output_language", "Chinese"))
        selected = cfg.get("selected_analysts", ["market", "social", "news", "fundamentals"])
        for key, var in self.analyst_vars.items():
            var.set(key in selected)

    def _save_config(self):
        """Save current configuration to config.json."""
        cfg = self._get_current_config()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            self.status_var.set(f"配置已保存到 {CONFIG_FILE}")
            self._log(f"[INFO] 配置已保存到 {CONFIG_FILE}\n")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _load_config(self):
        """Load configuration from config.json if it exists."""
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._apply_config(cfg)
                self.config = cfg
            except Exception as e:
                self._log(f"[WARN] 加载配置失败: {e}\n")

    def _load_config_dialog(self):
        """Load configuration from a user-selected file."""
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=CONFIG_FILE,
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._apply_config(cfg)
                self.status_var.set(f"已加载: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("加载失败", str(e))

    def _log(self, text: str):
        """Append text to output area (thread-safe)."""
        self.output_text.after(0, self._log_impl, text)

    def _log_impl(self, text: str):
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)

    def _run_analysis(self):
        """Start analysis in background thread."""
        cfg = self._get_current_config()

        # Validation
        if not cfg["api_key"]:
            messagebox.showwarning("缺少配置", "请输入 API Key")
            return
        if not cfg["ticker"]:
            messagebox.showwarning("缺少配置", "请输入分析标的 (Ticker)")
            return
        if not cfg["selected_analysts"]:
            messagebox.showwarning("缺少配置", "请至少选择一个分析师")
            return

        # Save config before running
        self._save_config()

        self.running = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set("分析中...")
        self.output_text.delete("1.0", tk.END)

        thread = threading.Thread(target=self._analysis_worker, args=(cfg,), daemon=True)
        thread.start()

    def _stop_analysis(self):
        """Signal to stop analysis."""
        self.running = False
        self.status_var.set("正在停止...")

    def _test_relay(self):
        """Test relay/API connectivity in a background thread."""
        base_url = self.backend_url_var.get().strip()
        api_key = self.api_key_var.get().strip()
        model = self.quick_model_var.get().strip() or "gpt-4o-mini"

        if not api_key:
            messagebox.showwarning("缺少配置", "请先填写 API Key")
            return

        self.status_var.set("正在测试连接...")
        self._log("\n[TEST] 正在测试中转站连接...\n")
        if base_url:
            self._log(f"[TEST] URL: {base_url}\n")
        self._log(f"[TEST] 模型: {model}\n")

        def worker():
            import httpx
            url = (base_url.rstrip("/") + "/chat/completions") if base_url else "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "请用一句话回复：测试成功"}],
                "max_tokens": 50,
            }
            try:
                client = httpx.Client(verify=False, timeout=30)
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "(空回复)")
                    self._log(f"[TEST] ✓ 连接成功! 状态码: {resp.status_code}\n")
                    self._log(f"[TEST] AI 回复: {content}\n")
                    self.root.after(0, lambda: self.status_var.set("连接测试成功 ✓"))
                else:
                    self._log(f"[TEST] ✗ 请求失败! 状态码: {resp.status_code}\n")
                    self._log(f"[TEST] 响应: {resp.text[:500]}\n")
                    self.root.after(0, lambda: self.status_var.set(f"连接失败: HTTP {resp.status_code}"))
            except Exception as e:
                self._log(f"[TEST] ✗ 连接失败: {e}\n")
                self.root.after(0, lambda: self.status_var.set("连接测试失败 ✗"))

        threading.Thread(target=worker, daemon=True).start()

    def _analysis_worker(self, cfg: dict):
        """Run TradingAgents in background."""
        try:
            self._log(f"[INFO] 开始分析 {cfg['ticker']} (日期: {cfg['trade_date']})\n")
            self._log(f"[INFO] Provider: {cfg['llm_provider']}, 模型: {cfg['deep_think_llm']} / {cfg['quick_think_llm']}\n")
            if cfg["backend_url"]:
                self._log(f"[INFO] 中转站: {cfg['backend_url']}\n")
            self._log("-" * 60 + "\n")

            # Set API key in environment
            api_key = cfg["api_key"]
            provider = cfg["llm_provider"]

            env_key_map = {
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "qwen": "DASHSCOPE_API_KEY",
                "glm": "ZHIPU_API_KEY",
                "xai": "XAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "google": "GOOGLE_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
            }
            env_var = env_key_map.get(provider, "OPENAI_API_KEY")
            os.environ[env_var] = api_key

            # Set BlockBeats API key
            bb_key = cfg.get("blockbeats_api_key", "")
            if bb_key:
                os.environ["BLOCKBEATS_API_KEY"] = bb_key

            # Import here to avoid slow startup
            from tradingagents.graph.trading_graph import TradingAgentsGraph
            from tradingagents.default_config import DEFAULT_CONFIG

            # Build runtime config
            runtime_config = DEFAULT_CONFIG.copy()
            runtime_config["llm_provider"] = provider
            runtime_config["deep_think_llm"] = cfg["deep_think_llm"]
            runtime_config["quick_think_llm"] = cfg["quick_think_llm"]
            runtime_config["max_debate_rounds"] = cfg["max_debate_rounds"]
            runtime_config["max_risk_discuss_rounds"] = cfg["max_risk_discuss_rounds"]
            runtime_config["output_language"] = cfg["output_language"]

            if cfg["backend_url"]:
                runtime_config["backend_url"] = cfg["backend_url"]

            self._log("[INFO] 初始化 TradingAgentsGraph...\n")

            ta = TradingAgentsGraph(
                selected_analysts=cfg["selected_analysts"],
                debug=True,
                config=runtime_config,
            )

            if not self.running:
                self._log("[INFO] 用户取消\n")
                return

            self._log("[INFO] 开始多 Agent 分析流程...\n\n")

            _, decision = ta.propagate(cfg["ticker"], cfg["trade_date"])

            self._log("\n" + "=" * 60 + "\n")
            self._log("【最终交易决策】\n")
            self._log("=" * 60 + "\n")
            self._log(str(decision) + "\n")

            self.root.after(0, lambda: self.status_var.set("分析完成 ✓"))

        except Exception as e:
            import traceback
            self._log(f"\n[ERROR] {e}\n")
            self._log(traceback.format_exc())
            self.root.after(0, lambda: self.status_var.set("分析失败 ✗"))

        finally:
            self.running = False
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))


def main():
    root = tk.Tk()
    app = TradingAgentsGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
