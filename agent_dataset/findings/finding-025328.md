---
id: 25328
severity: "Crit/High"
---

# Fixed term loans can be deployed with a wrong fee manager and possibly steal all funds.

## Description

In MapleLoanInitializer, the address of the fee manager is not whitelisted. Exploit scenario

- Borrower agrees with delegate on the terms and creates a loan with the correct fee manager;
- Attacker sees the transaction and creates a loan with the same arguments, changing only the fee manager address. They can even choose a salt that makes the first bytes of the malicious loan contract equal to the valid loan contract;
- The pool delegate sees the malicious loan address and funds it thinking it is the valid one;
- All funds are sent to the attacker.

## Proof of Concept

No PoC provided.

## Recommendation

Whitelist the Fee Manager by adding an isInstanceOf check in MapleGlobals.
