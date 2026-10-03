---
id: 25181
severity: "Low/Info"
---

# BaseRouter, _bundleInternal(...) Action.Flashloan does not check if the selector matches xBundle(...)

## Description

Users make flashloans by calling xBundle(...) with a flashloan action. When the flashloan calls the callback of the Flasher, in _requestorExecution(...) of the BaseFlasher, it calls the function selector in the first 4 bytes in the requestorCalldata.

However, in _bundleInternal(...), the correct selector is not enforced, so users can call any function of the BaseRouter. There does not seem to be any clear path for an exploit, but it's best to check.

## Proof of Concept

No PoC provided.

## Recommendation

Add if (bytes4(LibBytes.slice(requesterCalldata, 0, 4)) != this.xBundle(...).selector) revert(); or similar.
