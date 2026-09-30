---
id: 17637
severity: "High"
---

# Surplus auction cannot be cancelled

## Description

Attempts to cancel surplus auctions will likely fail because approval is required, but not given.  
Instead of performing a conventional transfer(), the token's transferFrom() function is called:  
```solidity
token.transferFrom(address(this), auctions[auctionId].recipient, auctions[auctionId].bid);
```  
However, approval needs to be given to the caller, even if the caller is the token sender. This is the case for OpenZeppelin's ERC20 implementation (which FDT inherits). A snippet of the transferFrom() function is given below.  
```solidity
_transfer(sender, recipient, amount);
uint256 currentAllowance = _allowances[sender][_msgSender()];
require(currentAllowance >= amount, "ERC20: transfer amount exceeds allowance");
```  
Because zero allowance has been given, the transaction will revert.  
Surplus auctions cannot be cancelled.

## Proof of Concept

no poc

## Recommendation

Change to transfer() or OpenZeppelin's safeTransfer() methods.  
```solidity
token.transfer(auctions[auctionId].recipient, auctions[auctionId].bid);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition in the surplus‑auction cancellation flow of the protocol. When a caller attempts to cancel an active surplus auction, the contract invokes the ERC‑20 token’s transferFrom function to move the winning bid back to the auction recipient. TransferFrom requires that the caller have a non‑zero allowance set by the token holder (the contract itself in this case). Because the contract never grants itself an allowance, the internal allowance check fails and the transaction reverts with \"ERC20: transfer amount exceeds allowance\". Consequently the cancellation transaction cannot succeed and the auction remains open indefinitely. The root cause is a misuse of the ERC‑20 transferFrom API: the developers assumed that a contract could pull its own tokens without an explicit approval, which is contrary to the OpenZeppelin ERC‑20 implementation that enforces allowance checks even when the sender and the caller are the same address. An attacker or any user who triggers the cancel function can therefore block the auction, preventing the protocol from reclaiming surplus funds. This may lead to funds being locked in the auction contract, users seeing no refund or payout, and the overall accounting of the system becoming inconsistent because expected surplus balances never clear. The issue appears only when the cancel path is exercised; normal auction creation and bidding work because they do not call transferFrom. It was discovered during a manual security audit that inspected the cancelAuction logic and compared it against the ERC‑20 token contract. The problem is subtle because transferFrom is a common pattern for moving tokens and developers may overlook the allowance requirement when the contract itself is the token holder. To remediate, the contract should replace the transferFrom call with a direct transfer (or OpenZeppelin’s safeTransfer) which does not require an allowance, thereby allowing the contract to move its own tokens and successfully cancel the auction. This change restores the intended business logic that surplus auctions can be cancelled and that surplus funds are returned to the designated recipient, aligning the implementation with the protocol’s accounting assumptions.
