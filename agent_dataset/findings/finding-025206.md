---
id: 25206
severity: "Low/Info"
---

# _tempTokenToCheck in BaseRouter does not need to be a state variable

## Description

_tempTokenToCheck checks that the balance of the ConnextRouter does not change after having received tokens in xReceive(...) . This variable is unnecessary as the tokensToCheck variable of _bundleInternal(...) could be created before the _bundleInternal(...) call and passed as argument.

## Proof of Concept

No PoC provided.

## Recommendation

In the ConnextRouter, create the tokensToCheck variable in the xReceive(...) function and pass it as argument to xBundleConnext(...), which should pass it as argument to _bundleInternal(...). In the BaseRouter, create the tokensToCheck variable in xBundle(...) and pass it as argument to _bundleInternal(...).
