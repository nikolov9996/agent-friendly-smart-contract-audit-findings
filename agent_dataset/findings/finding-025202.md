---
id: 25202
severity: "Medium"
---

# Connext delegates can perform important actions, make sure smart contract users implement them

## Description

Connext implements a mechanism of adjusting/forcing parameters in the bridged assets which can be triggered by a delegate. If the delegate is a EOA or wallet, there is no problem, as the delegate can call directly the connext bridge.

However, care must be taken if the caller of xBundle(...) is a smart contract, in which it may not implement the necessary Connext function calls. This can be dangerous if the smart contract user set, for example, a low slippage tolerance and did not implement the function forceUpdateSlippage(...) of the connext bridge.

## Proof of Concept

No PoC provided.

## Recommendation

Implement methods in the Router/Handler to handle these function calls, such as bumpTransfer(...) and make the ConnextRouter the delegate. In alternative, make it very clear in the documentation and comments in the interface/code that the user must implement these important Connext methods if it is a smart contract.
