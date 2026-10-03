# Architecture

```text
Customer
   |
   v
Input Firewall -----> injection / legal / safety signals
   |
   v
Intent Parser ------> single or multiple intents
   |
   v
Context Resolver ---> authenticated customer + conversations + tickets
   |
   v
Entity Verifier ----> ownership + current order/product state
   |
   +-----------> Policy Compiler / Version Resolver
   |
   +-----------> Exact DB retrieval / Product RAG
   |
   v
Intent DAG / Decision Engine
   |
   +---- ANSWER
   +---- ASK
   +---- ACT ----> Proof / Action Guard ----> Tool ----> Post-condition verification
   +---- ESCALATE ----------------------------> Human queue + ticket
   |
   v
Response Composer
```

### Trust boundary

System rules and policies have higher authority than customer content. The database and verified tool responses provide truth. Customer statements are evidence requests/claims until verified.

### Why the architecture is layered

The handbook separates intent, memory, policy, tools and decision responsibilities. The implementation preserves that separation so each hidden-test family maps to an explicit component rather than a fragile prompt rule.
