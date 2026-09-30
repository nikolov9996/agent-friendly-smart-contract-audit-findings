---
id: 17816
severity: "High"
---

# Netting and withdraw auction can be frozen

## Description

An attacker can permanently block the auctions by using a blocked address to fail USDC transfers, which are now required for the auction to proceed. Say Bob knows that one of his addresses is blocked by USDC. He has/can obtain CRAB, which he can transfer to this address. As withdraw queue requires each transfer call to be successful, this will permanently freezes the functionality, i.e. all future auctions will be blocked. Knowing that, Bob will block the auctions when it's beneficial to him the most. netAtPrice() and withdrawAuction() will be blocked as long as Bob's withdrawal is queued. There is no way for the owner to manually alter this state. As auction timing can have material impact on the beneficiaries, the inability to perform netting and withdraw auction will lead to losses for them as Bob will choose the moment to execute the attack to benefit himself at the expense of the participants. Setting the severity to be high as this is permanent freeze of the core functionality fully controllable by the attacker only.

netAtPrice() will be reverting at Bob's withdrawal:
Netting.sol#L389-L419
```solidity
// process withdraws and send usdc
i = withdrawsIndex;
while (crabQuantity > 0) {
    Receipt memory withdraw = withdraws[i];
    if (withdraw.amount == 0) {
        i++;
        continue;
    }
    if (withdraw.amount <= crabQuantity) {
        crabQuantity = crabQuantity - withdraw.amount;
        crabBalance[withdraw.sender] -= withdraw.amount;
        amountToSend = (withdraw.amount * _price) / 1e18;
        IERC20(usdc).transfer(withdraw.sender, amountToSend);
        emit CrabWithdrawn(withdraw.sender, withdraw.amount, amountToSend, i);
        delete withdraws[i];
        i++;
    } else {
        withdraws[i].amount = withdraw.amount - crabQuantity;
        crabBalance[withdraw.sender] -= crabQuantity;
        amountToSend = (crabQuantity * _price) / 1e18;
        IERC20(usdc).transfer(withdraw.sender, amountToSend);
        emit CrabWithdrawn(withdraw.sender, withdraw.amount, amountToSend, i);
        crabQuantity = 0;
    }
}
withdrawsIndex = i;
}
```
withdrawAuction() similarly will fail on Bob's entry:
Netting.sol#L687-L720
```solidity
// step 5 pay all withdrawers and mark their withdraws as done
uint256 remainingWithdraws = _p.crabToWithdraw;
uint256 j = withdrawsIndex;
uint256 usdcAmount;
while (remainingWithdraws > 0) {
    Receipt memory withdraw = withdraws[j];
    if (withdraw.amount == 0) {
        j++;
        continue;
    }
    if (withdraw.amount <= remainingWithdraws) {
        // full usage
        remainingWithdraws -= withdraw.amount;
        crabBalance[withdraw.sender] -= withdraw.amount;
        // send proportional usdc
        usdcAmount = (((withdraw.amount * 1e18) / _p.crabToWithdraw) * usdcReceived) / 1e18;
        IERC20(usdc).transfer(withdraw.sender, usdcAmount);
        emit CrabWithdrawn(withdraw.sender, withdraw.amount, usdcAmount, j);
        delete withdraws[j];
        j++;
    } else {
        withdraws[j].amount -= remainingWithdraws;
        crabBalance[withdraw.sender] -= remainingWithdraws;
        // send proportional usdc
        usdcAmount = (((remainingWithdraws * 1e18) / _p.crabToWithdraw) * usdcReceived) / 1e18;
        IERC20(usdc).transfer(withdraw.sender, usdcAmount);
        emit CrabWithdrawn(withdraw.sender, remainingWithdraws, usdcAmount, j);
        remainingWithdraws = 0;
    }
}
withdrawsIndex = j;
```
netAtPrice() and withdrawAuction() unavailability and the whole withdrawal queue freeze will be permanent as withdrawsIndex can be changed only in netAtPrice() and withdrawAuction(), i.e. there is no way to skip any entry, including Bob's. I.e. only Bob can unstuck the system by removing the withdrawal:
Netting.sol#L319-L346
```solidity
/**
* @notice withdraw Crab from queue
* @param _amount Crab amount to dequeue
*/
function dequeueCrab(uint256 _amount) external {
    require(!isAuctionLive, "auction is live");
    crabBalance[msg.sender] = crabBalance[msg.sender] - _amount;
    require(
        crabBalance[msg.sender] >= minCrabAmount || crabBalance[msg.sender] == 0,
        "remaining amount smaller than minimum, consider removing full balance"
    );
    // deQueue crab from the last, last in first out
    uint256 toRemove = _amount;
    uint256 lastIndexP1 = userWithdrawsIndex[msg.sender].length;
    for (uint256 i = lastIndexP1; i > 0; i--) {
        Receipt storage r = withdraws[userWithdrawsIndex[msg.sender][i - 1]];
        if (r.amount > toRemove) {
            r.amount -= toRemove;
            toRemove = 0;
            break;
        } else {
            toRemove -= r.amount;
            delete withdraws[userWithdrawsIndex[msg.sender][i - 1]];
        }
    }
    IERC20(crab).transfer(msg.sender, _amount);
    emit CrabDeQueued(msg.sender, _amount, crabBalance[msg.sender]);
}
```

## Proof of Concept

no poc

## Recommendation

Consider trying to transfer and skipping if there is any malfunction, for example:
Netting.sol#L389-L419
```solidity
// process withdraws and send usdc
i = withdrawsIndex;
while (crabQuantity > 0) {
    Receipt memory withdraw = withdraws[i];
    if (withdraw.amount == 0) {
        i++;
        continue;
    }
    if (withdraw.amount <= crabQuantity) {
        amountToSend = (withdraw.amount * _price) / 1e18;
        try IERC20(usdc).transfer(withdraw.sender, amountToSend) {
            crabQuantity = crabQuantity - withdraw.amount;
            crabBalance[withdraw.sender] -= withdraw.amount;
            emit CrabWithdrawn(withdraw.sender, withdraw.amount, amountToSend, i);
            delete withdraws[i];
        } catch {
        }
        i++;
    } else {
        amountToSend = (crabQuantity * _price) / 1e18;
        try IERC20(usdc).transfer(withdraw.sender, amountToSend) {
            withdraws[i].amount = withdraw.amount - crabQuantity;
            crabBalance[withdraw.sender] -= crabQuantity;
            emit CrabWithdrawn(withdraw.sender, withdraw.amount, amountToSend, i);
            crabQuantity = 0;
        } catch {
            i++;
        }
    }
}
withdrawsIndex = i;
}
```
This can be paired with introduction of the onlyOwner rescue function to handle the transfer manually, say for USDC ban case: auction operator transfers to self, swaps and return the funds to depositor in another form. Notice that skipping the entry causes no harm for the withdrawer as dequeueCrab() can be run any time for it.

## Derived Narrative

The following field is derived content and may not be source-grounded:

An attacker can permanently freeze the netting and withdraw auction mechanisms by inserting a withdrawal entry that points to an address unable to receive USDC. The contract processes pending withdrawals in a linear queue and calls IERC20(usdc).transfer for each entry. Because the code does not catch a failed transfer, a revert caused by a blocked address stops the entire loop, leaving withdrawsIndex pointing at the failing entry. No later withdrawals or auction settlements can advance past this point, and the contract provides no owner‑only function to skip or remove the stuck entry. The condition occurs when a USDC transfer to a particular address reverts – for example, if the address is on USDC’s compliance blocklist. An attacker who controls such a blocked address can deposit CRAB tokens, request a withdrawal, and then wait until an auction is about to settle. When netAtPrice() or withdrawAuction() runs, the transfer to the blocked address fails, the function reverts, and the protocol’s core functionality is halted indefinitely. Users experience symptoms such as “my withdrawal never completes”, “auction does not finish”, or “no USDC is received despite a pending claim”. The impact is a denial‑of‑service that prevents all participants from receiving their proportional USDC, potentially causing financial loss for beneficiaries and undermining confidence in the protocol. The issue was discovered during a manual audit that examined the withdrawal loop and noted the lack of error handling for external token transfers. It is hard to notice because USDC transfers normally succeed, so the failure only appears under rare compliance blocks. The bug belongs to the class of “unhandled external call failures leading to permanent queue lock”. To remediate, the contract should handle transfer failures gracefully, for example by using try/catch around the ERC20 transfer, skipping the offending entry, or providing an owner‑only rescue function that can manually settle or remove stuck withdrawals. Such a fix restores progress of the queue and ensures that a single blocked address cannot halt the entire auction process.
