---
id: 18653
severity: "High"
---

# `ParticleExchange.auctionBuyNft` and `ParticleExchange.withdrawEthWithInterest` function calls can be DOS’ed

## Description

```solidity
When `lien.borrower` is a contract, its `receive` function can be coded to conditionally revert based on a state boolean variable controlled by `lien.borrower`’s owner. As long as `payback > 0` is true, `lien.borrower`’s `receive` function would be called when calling the following `ParticleExchange.auctionBuyNft` function. In this situation, if the owner of `lien.borrower` intends to DOS the `ParticleExchange.auctionBuyNft` function call, especially when `lien.credit` is low or 0, she or he would make `lien.borrower`’s `receive` function revert.

    function auctionBuyNft(
        Lien calldata lien,
        uint256 lienId,
        uint256 tokenId,
        uint256 amount
    ) external override validateLien(lien, lienId) auctionLive(lien) {
        ...

        // pay PnL to borrower
        uint256 payback = lien.credit + lien.price - payableInterest - amount;
        if (payback > 0) {
            payable(lien.borrower).transfer(payback);
        }

        ...
    }
```

Moreover, after the auction of the lien is concluded, calling the following `ParticleExchange.withdrawEthWithInterest` function can call `lien.borrower`’s `receive` function, as long as `lien.credit > payableInterest` is true. In this case, the owner of `lien.borrower` can also make `lien.borrower`’s `receive` function revert to DOS, the `ParticleExchange.withdrawEthWithInterest` function call.
```solidity
    function withdrawEthWithInterest(Lien calldata lien, uint256 lienId) external override validateLien(lien, lienId) {
        ...

        uint256 payableInterest = _calculateCurrentPayableInterest(lien);

        // verify that the liquidation condition has met (borrower insolvent or auction concluded)
        if (payableInterest < lien.credit && !_auctionConcluded(lien.auctionStartTime)) {
            revert Errors.LiquidationHasNotReached();
        }

        // delete lien (delete first to prevent reentrancy)
        delete liens[lienId];

        // transfer ETH with interest back to lender
        payable(lien.lender).transfer(lien.price + payableInterest);

        // transfer PnL to borrower
        if (lien.credit > payableInterest) {
            payable(lien.borrower).transfer(lien.credit - payableInterest);
        }

        ...
    }
```

Similar situations can happen if `lien.borrower` does not implement the `receive` or `fallback` function intentionally; in which `lien.borrower`’s owner is willing to pay some position margin, which can be a low amount depending on the corresponding lien, to DOS the `ParticleExchange.auctionBuyNft` and `ParticleExchange.withdrawEthWithInterest` function calls.

## Proof of Concept

```solidity
The following steps can occur for the described scenario for the `ParticleExchange.auctionBuyNft` function. The situation for the `ParticleExchange.withdrawEthWithInterest` function is similar:

1. Alice is the owner of `lien.borrower` for a lien.
2. The lender of the lien starts the auction for the lien.
3. Alice does not want the auction to succeed, so she makes `lien.borrower`’s `receive` function revert by changing the controlled state boolean variable for launching the DOS attack to true.
4. For a couple of times during the auction period, some other users are willing to win the auction by supplying an NFT from the same collection, but their `ParticleExchange.auctionBuyNft` function calls all revert.
5. Since no one’s `ParticleExchange.auctionBuyNft` transaction is executed at the last second of the auction period, the auction is DOS’ed.
```

## Recommendation

```solidity
The `ParticleExchange.auctionBuyNft` and `ParticleExchange.withdrawEthWithInterest` functions can be updated to record the `payback` and `lien.credit - payableInterest` amounts that should belong to `lien.borrower`, instead of directly sending these amounts to `lien.borrower`. Then, a function can be added to let `lien.borrower` call and receive these recorded amounts.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service (DoS) condition that arises when the ParticleExchange contract attempts to send Ether directly to the borrower of a lien using the .transfer call in both the auctionBuyNft and withdrawEthWithInterest functions. The root cause is the assumption that a .transfer will always succeed; however, if the borrower address is a contract whose receive (or fallback) function can deliberately revert based on an internal boolean flag, the transfer will fail and cause the whole transaction to revert. This can be triggered whenever the calculated payback amount is greater than zero in auctionBuyNft or when the borrower’s remaining credit exceeds the payable interest in withdrawEthWithInterest. An attacker who controls the borrower contract (for example, the owner of the contract) can set the flag so that the receive function reverts, or simply omit a receive/fallback implementation, causing the transfer to revert automatically. By doing so, the attacker can block the execution of auctionBuyNft, preventing any participant from successfully purchasing the NFT and completing the auction, and can also block withdrawEthWithInterest, preventing the lender from retrieving the principal plus interest after liquidation. The impact is that the auction may never conclude, funds remain locked in the contract, lenders cannot recover their capital, and borrowers do not receive the expected payout, effectively breaking the business logic of the marketplace. The condition occurs only when the borrower is a contract capable of rejecting Ether transfers and when the protocol logic reaches a branch that attempts to pay the borrower. It was discovered during a manual audit that examined the flow of Ether transfers and considered the behavior of external contracts. The issue is subtle because .transfer is often regarded as a safe, gas‑limited method, and developers may not anticipate that a malicious or mis‑configured contract can cause a revert, leading to a hidden DoS vector. To remediate, the contract should adopt a pull‑payment pattern: instead of sending Ether directly, it should record the amount owed to the borrower in a mapping and provide a separate function that the borrower can call to withdraw the funds. This eliminates the reliance on the borrower’s receive function and prevents the auction and withdrawal processes from being blocked by a single contract’s revert behavior.
