---
id: 25736
severity: "Low/Info"
---

# Risk parameters should include additional checks to prevent mistakes

## Description

Risk parameters should be lower, higher or equal to 1e18, depending if short or long. For example, the long risk values should be smaller or equal to 1e18, or some of the functionality may get corrupted.

In SpotEngine::decomposeLps(), [rewards](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/SpotEngineLP.sol#L175-L182>) are calculated as amountQuote * (1e18 - short/longMaintenanceWeight). amountQuote is expected to be a positive value, thus the selected weight will be long.

Thus, if longWeightMaintenanceX18 > 1e18, rewards will be negative and the liquidatee earns these rewards.

## Proof of Concept

No PoC provided.

## Recommendation

Place explicit checks when [setting](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/BaseEngine.sol#L260>) the risk parameters in BaseEngine::_addProductForId() .
