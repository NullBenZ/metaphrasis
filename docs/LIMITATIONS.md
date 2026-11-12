# Limitations and verification gaps

## Fortran inputs

- The analyzer supports only the five recognized stencil families and their constrained expression/boundary forms. It is not a general Fortran-to-Devito compiler.
- Explicit loop strides are rejected; loop structures other than the recognized nested grid loops and outer timestep/iteration loop are rejected.
- Array bounds must start at zero for emission. Unsupported declarations, initial conditions, boundary conditions, coefficient expressions, and shapes are reported as unsupported or fail emission; the converter does not infer missing values.
- Generated templates preserve the fixture conventions. Broader combinations such as nonzero initial previous wavefield, unusual boundary equations, nonuniform grids, or alternative array layouts have not been established by the current test set.
- Numeric coverage includes base fixtures and the deterministic generated variants in the generalization CSV. It does not establish correctness for arbitrary programs. Fortran single-precision and Devito data-type behavior can require tolerance selection; tolerances are explicit command options.

## Devito API and repository index

- The API-name allow-list and idiom citations are derived from one pinned Devito checkout. They do not prove semantic compatibility with other releases or every legal API usage.
- The emitter uses fixed local templates. It does not synthesize arbitrary Devito operators from repository code.
- An index must be rebuilt after changing the repository revision; stale indexes can give stale names and idiom paths.

## Retrieval labels and recall

- `data/queries.jsonl` contains 20 DRAFT queries with no reviewed relevance judgments. Real-query Precision@5, Recall@5, MRR, and pre-screen recall remain unverified until labels are added with `metagraph.label_queries`.
- Synthetic-corpus retrieval metrics are not Devito retrieval quality measurements.
- The current pre-screen ranks communities using BM25-hit counts. Its usefulness depends on the query and reviewed relevance labels.

## Graph algorithms and measurements

- Top-K is exact and pairwise, so it scales quadratically in vertex comparisons. Dense mode retains all positive similarities and can use quadratic time, memory, and disk; full-repository dense experiments may be impractical on some machines.
- Leiden reference agreement is verified on the fixed test graphs and resolutions described in `docs/EXPLAIN.md`, not proven for every graph or seed.
- Thread and wall-clock measurements vary with machine load, compiler, and filesystem. Sampled RSS can miss short-lived peaks. Synthetic results must not be presented as Devito results.
- No speedup claim from the report is treated as established. A ratio is reported only after both compared runs finish successfully.
- The real-data benchmark currently uses portions of the indexed Devito vector rows for graph-size sweeps; those are sampled real data. It does not create synthetic points below/within the repository range.

## Runtime and environment

- Numeric validation requires gfortran, a working Devito import path, and a supported JIT compiler/toolchain. The benchmarking scripts require C++17, CMake, NumPy, and matplotlib; reference checks additionally require `leidenalg`/`igraph`.
- The clean-machine workflow requires network access for cloning the pinned Devito commit. If unavailable, clone/index cannot be verified and must be skipped rather than replaced with fabricated data.
- This workspace's `.git` metadata is read-only for the assistant session. No GitHub writes were made. `scripts/first_commit.sh` displays commands for the user to run manually.

## Current full-dense run

A full `--dense` run over all indexed Devito rows was attempted but did not finish during the available run and was interrupted. No full-index dense retrieval ratio is claimed. The real-data benchmark therefore defaults to dense sweeps capped at half the indexed rows, records skipped larger dense sizes, and labels the retrieval comparison with the actual row count; pass `--dense-limit` to request a different limit. Query recall is unverified until reviewer labels exist.
