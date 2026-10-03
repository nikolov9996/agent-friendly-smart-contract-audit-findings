---
id: 25340
severity: "Medium"
---

# Malicious refinancer danger due to fixed term loan upgrades.

## Description

In the previous [maple-core-v2 code,](<https://github.com/maple-labs/loan/blob/16d50af0af22b4725073eea76a1e27da60b385e4/contracts/MapleLoan.sol#L215>) any address could be chosen for the refinancer when proposing new terms.

The new versions of the fixed term loans add a check regarding the refinancer address, but place it in the proposeNewTerms(...) function, such that proposed terms in the previous loans version did not validate the refinancer address.

The new check could lead to a false sense of security and delegates could accept new terms with a malicious refinancer address. Exploit

- v400 fixed term loan borrower proposes refinancing with an invalid fee manager
- v400 loans are upgraded to v500 loans
- Given that v500 loans only allow whitelisted refinancers to be proposed, it could lead to a false sense of security
- The delegate accepts the new terms and the malicious refinancer address steals funds

## Proof of Concept

No PoC provided.

## Recommendation

The refinancer validation should be done on acceptNewTerms(...). It would be possible to leave it on proposeNewTerms(...), however, it would require the Maple team to track all the v400 maple loans (even the ones that were not funded / are idle) to check if there are invalid refinancer addresses before upgrading, and even then, attackers could still watch the mempool for the upgrade.

Overall, it is safer to put the validation on acceptNewTerms(...).
