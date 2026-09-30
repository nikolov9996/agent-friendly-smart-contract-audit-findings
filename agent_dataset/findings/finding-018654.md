---
id: 18654
severity: "High"
---

# Treasury fee is not collected in `withdrawEthWithInterest`

## Description

```solidity
The Particle exchange collects treasury fees from the lender’s interests. These interests are accumulated in the `interestAccrued` mapping and are withdrawn using the `_withdrawAccountInterest()` function, which splits the portion that corresponds to the treasury.

    function _withdrawAccountInterest(address payable lender) internal {
        uint256 interest = interestAccrued[lender];
        if (interest == 0) return;

        interestAccrued[lender] = 0;

        if (_treasuryRate > 0) {
            uint256 treasuryInterest = MathUtils.calculateTreasuryProportion(interest, _treasuryRate);
            _treasury += treasuryInterest;
            interest -= treasuryInterest;
        }

        lender.transfer(interest);

        emit WithdrawAccountInterest(lender, interest);
    }
```

Lines 238-240 calculate treasury fees and accumulate them in the `_treasury` variable, which is later withdrawn by the owner using the `withdrawTreasury()` function.

However, these fees fail to be considered in the case of `withdrawEthWithInterest()`:
```solidity
    function withdrawEthWithInterest(Lien calldata lien, uint256 lienId) external override validateLien(lien, lienId) {
        if (msg.sender != lien.lender) {
            revert Errors.Unauthorized();
        }

        if (lien.loanStartTime == 0) {
            revert Errors.InactiveLoan();
        }

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

        emit WithdrawETH(lienId);

        // withdraw interest from this account too
        _withdrawAccountInterest(payable(msg.sender));
    }
```

As we can see in the previous snippet of code, the interests are calculated in line 201, but that amount is then transferred, along with the lien price, back to the lender in full in line 212, without deducting any treasury fees.

## Proof of Concept

no poc

## Recommendation

```solidity
The interest can be simply accumulated in the `interestAccrued` mapping, which is later withdrawn (correctly taking into account treasury fees) in the already present call to `_withdrawAccountInterest()`.
    
    function withdrawEthWithInterest(Lien calldata lien, uint256 lienId) external override validateLien(lien, lienId) {
        if (msg.sender != lien.lender) {
            revert Errors.Unauthorized();
        }

        if (lien.loanStartTime == 0) {
            revert Errors.InactiveLoan();
        }

        uint256 payableInterest = _calculateCurrentPayableInterest(lien);

        // verify that the liquidation condition has met (borrower insolvent or auction concluded)
        if (payableInterest < lien.credit && !_auctionConcluded(lien.auctionStartTime)) {
            revert Errors.LiquidationHasNotReached();
        }

        // delete lien (delete first to prevent reentrancy)
        delete liens[lienId];
        
        // accrue interest to lender
        interestAccrued[lien.lender] += payableInterest;

        // transfer ETH back to lender
        payable(lien.lender).transfer(lien.price);

        // transfer PnL to borrower
        if (lien.credit > payableInterest) {
            payable(lien.borrower).transfer(lien.credit - payableInterest);
        }

        emit WithdrawETH(lienId);

        // withdraw interest from this account too
        _withdrawAccountInterest(payable(msg.sender));
    }
```

We will likely fix the issue in another way. We will modify `withdrawNftWithInterest` and `withdrawEthWithInterest` into `withdrawNft` and `withdrawEth`, i.e. move the interest withdraw into the single account level interest withdraw function (similar to the suggestion made in <https://github.com/code-423n4/2023-05-particle-findings/issues/31>).

After discussion, I think that High is the appropriate severity because this issue incurs loss for the protocol.

Fixed.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the withdrawEthWithInterest function, which is intended to return a lender’s principal together with the accrued interest after a liquidation event. The contract maintains a separate accounting mechanism for interest in the interestAccrued mapping, and the internal _withdrawAccountInterest routine applies the configured treasury fee before sending the net interest to the lender. In withdrawEthWithInterest the code calculates the payable interest, but then transfers the full interest amount directly to the lender together with the lien price, bypassing the interestAccrued mapping entirely. Because the treasury fee is only deducted when interest is withdrawn through _withdrawAccountInterest, the fee is never taken from the amount sent in this path. After the transfer the function still calls _withdrawAccountInterest, but at that point the lender’s accrued interest balance is zero, so the treasury receives nothing. This logical omission means that every time a lender withdraws ETH with interest, the protocol’s treasury does not collect its proportional fee, leading to a systematic loss of revenue. The issue manifests only when the withdrawEthWithInterest function is executed, i.e., after a loan has been liquidated and the lender invokes the withdrawal. Users see the expected outcome – they receive their principal plus the full interest – so the bug is not obvious from the UI; the missing treasury fee is hidden in the contract’s internal accounting. The problem was discovered during a manual audit that compared the interest handling in _withdrawAccountInterest with the direct transfer in withdrawEthWithInterest. It is hard to notice because there is no error or revert, only a discrepancy between the treasury’s recorded balance and the protocol’s intended fee model. The correct mitigation is to treat the interest in withdrawEthWithInterest the same way as other withdrawals: record the payable interest in the interestAccrued mapping, then invoke _withdrawAccountInterest so that the treasury proportion is deducted before the net amount is sent to the lender. Alternatively, the function can be refactored to a generic withdraw routine that relies on the single account‑level interest withdrawal logic, ensuring the fee is always applied.
