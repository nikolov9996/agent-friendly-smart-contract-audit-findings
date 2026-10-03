---
id: 25022
severity: "Crit/High"
---

# Cds depositors profit up to the strike price is not redeemable as the total cds deposited amount is not increased

## Description



## Proof of Concept

[Here](<https://github.com/sherlock-audit/2024-11-autonomint/blob/main/Blockchain/Blockchian/contracts/Core_logic/borrowing.sol#L665>) the upside is not added to the total cds deposited amount, which means that it will underflow when cds depositors withdraw the profit [here](<https://github.com/sherlock-audit/2024-11-autonomint/blob/main/Blockchain/Blockchian/contracts/lib/CDSLib.sol#L713>). The profit is added [here](<https://github.com/sherlock-audit/2024-11-autonomint/blob/main/Blockchain/Blockchian/contracts/Core_logic/CDS.sol#L343>).

## Recommendation

Add the upside to `omniChainData.totalCdsDepositedAmount`.
