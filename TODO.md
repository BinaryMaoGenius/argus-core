# TODO — Working Memory contract (LRU+tokens+tags)

- [ ] Inspect current working memory usage sites (who calls write(layer="working"))
- [ ] Refactor working memory in `app/memory/memory.py`:
  - [x] Add TagType + push(item, tag), evict(), get_context(budget)
  - [x] Implement LRU strict using OrderedDict (LRU = least recently accessed)
  - [x] Implement token budget using injectable token_counter + env-configured budget
  - [x] Implement eviction routing: structurant -> recall, non-structurant -> drop
  - [x] Move routing responsibility from evict() to push() (structurant written to recall immediately)
  - [x] Keep backward compatibility: adapt existing `write(..., layer="working")` to call push with default tag + warning/log

- [ ] Update call sites minimally if required to pass tags (or keep default for now)
- [x] Add unit tests in `tests/test_memory_kernel.py` for:
  - [x] eviction on budget exceed
  - [x] LRU ordering correctness
  - [x] routing based on tag (structurant -> recall, non-structurant -> lost)
- [x] Run pytest


