---
id: 25504
severity: "Low/Info"
---

# BRC20 parameters should be passed as arguments to the constructor of BRC20 to save gas

## Description

BRC20Factory::createBRC20() creates new BRC20 tokens by setting the parameters storage variable to the name, symbol and decimals of the new token, and then the BRC20 token in the constructor fetching this storage variable.

## Proof of Concept

No PoC provided.

## Recommendation

Send the name, symbol and decimals in the constructor to save gas, as create2 will work just as fine, but it becomes significantly cheaper to deploy the tokens.
