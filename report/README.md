# LLM-AS Conference Paper — DAA Mini Project
## Overleaf Student Reference | IEEE Two-Column Format

---

## Paper Topic
**"LLM-Guided Adaptive Algorithm Selection for the Travelling Salesman Problem"**

This paper bridges **LLMs + Algorithms (DAA)** by using a Large Language Model
(GPT-3.5-turbo) as an intelligent algorithm selector for the TSP — a core
NP-Hard problem studied in Design and Analysis of Algorithms.

---

## Project Files
```
llm_algo_conf_overleaf/
├── main.tex          ← Full IEEE conference paper (~8 pages)
├── references.bib    ← 22 BibTeX entries, IEEE format
└── README.md         ← This file
```

---

## How to Compile in Overleaf

1. **overleaf.com** → New Project → **Upload Project** → upload the ZIP
2. **Menu → Compiler → pdfLaTeX**
3. Click **Recompile** (run **twice** if references show as [?])

---

## Paper Structure (What to Study / Adapt)

| Section | Key Content |
|---------|-------------|
| **Abstract** | Problem → Approach → Key number results → Conclusion |
| **Introduction** | TSP motivation, NFL theorem, Algorithm Selection Problem, LLM background, 4 contributions |
| **Related Work** | 4 related papers + comparison table |
| **Methodology** | TSP formulation (Eq.1), ASP formulation (Eq.2), 6 instance features (table), LLM-AS architecture (TikZ flowchart), Prompt example (boxed), 5 portfolio algorithms with equations, Full pseudocode (Algorithm 1), Complexity analysis |
| **Experiments** | Setup, 4 instance type groups (table), 5 baselines, metrics, main results (table), bar chart by instance type (pgfplots), convergence plot (pgfplots), ablation study (table), Wilcoxon test (table), Discussion |
| **Conclusion** | 3-sentence summary + 5 future work bullets |

---

## LLM + Algorithms Connection (DAA Relevance)

The paper connects both topics explicitly:

| DAA Concept | How it appears in the paper |
|-------------|---------------------------|
| NP-Hard problems | TSP is NP-Hard (Section I) |
| Greedy algorithms | Nearest Neighbour heuristic (Section III-D) |
| Local search | 2-Opt with Δ-cost equation (Eq. 3) |
| Dynamic programming | Referenced as exact baseline |
| Metaheuristics | SA, GA, ACO with full equations |
| Time complexity | O(n²), O(T·Np·n) analysis (Section III-F) |
| Space complexity | O(Np·n) for population methods |
| Algorithm selection | Rice's ASP (1976) formalised |
| LLM as oracle | GPT-3.5-turbo as zero-shot/few-shot selector |

---

## LaTeX Features in this Paper

| Feature | Package / Command |
|---------|-------------------|
| IEEE two-column layout | `\documentclass[conference]{IEEEtran}` |
| Pseudocode | `algorithm` + `algorithmic` |
| Numbered equations | `\begin{equation}`, `\label{}`, `\eqref{}` |
| Bar chart (no image file) | `pgfplots` ybar axis |
| Line plot (no image file) | `pgfplots` standard axis |
| Flowchart (no image file) | `tikz` with node styles |
| Boxed prompt example | `\fbox{\parbox{...}{...}}` |
| Professional tables | `booktabs` + `tabularx` |
| Custom list labels | `enumitem` with `label=\textbf{C\arabic*.}` |
| Balanced columns | `\balance` before `\bibliographystyle` |
| Coloured hyperlinks | `hyperref` with `colorlinks=true` |

---

## How to Adapt for Your Own Topic

1. Change `\title{}` and `\author{}`  
2. Replace TSP with your problem in `\section{sec:method}` — update Eq. (1)  
3. Replace the 5 portfolio algorithms with your chosen algorithms  
4. Update `\begin{algorithm}` with your pseudocode  
5. Replace pgfplots coordinates with your actual experimental data  
6. Add references to `references.bib` and cite with `\cite{key}`  

> **Important:** Never fabricate experimental numbers. Use `N/R` for
> unreported values. Run at least 30 independent trials and report mean ± std.

---

## BibTeX Quick-Add Template
```bibtex
@article{authorYYYYkey,
  author  = {Last, First and Co-Author, Name},
  title   = {Paper Title Here},
  journal = {Journal / Conference Name},
  volume  = {X}, number = {Y}, pages = {start--end},
  year    = {YYYY}, doi = {10.xxxx/xxxxxxx}
}
```
