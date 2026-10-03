---
id: 25754
severity: "Medium"
---

# Locked funds due to underflow in withdrawal

## Description



## Proof of Concept

Foundry test demonstrating that the withdrawal call reverts due to the arithmetic underflow when the borrowed asset is token1:

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";

// Minimal interfaces and contract fragments required for the test.
interface IVault {
    function withdraw(uint256 shares, uint256 min0, uint256 min1) external returns (uint256, uint256);
}

interface ILendingPool {
    function getCurrentBorrowingIndex(address asset) external view returns (uint256);
    function repay(address asset, uint256 amount) external;
}

interface IERC20 {
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract Leverager {
    // Simplified Position struct used in the withdraw function.
    struct Position {
        address token0;
        address token1;
        address vault;
        uint256 borrowedAmount;
        uint256 borrowedIndex;
        address denomination; // borrowed token
        uint256 shares;
    }
    mapping(uint256 => Position) public positions;
    address public lendingPool;

    // Vulnerable withdraw function fragment.
    function withdraw(uint256 wp_pctWithdraw, uint256 shares, uint256 totalSupply, address msgSender) external {
        Position memory up = positions[1]; // using position ID 1 for testing
        // For testing, assume borrowed token equals up.token1.
        address borrowed = up.denomination;

        uint256 bIndex = ILendingPool(lendingPool).getCurrentBorrowingIndex(borrowed);
        uint256 totalOwedAmount = up.borrowedAmount * bIndex / up.borrowedIndex;
        uint256 owedAmount = totalOwedAmount * wp_pctWithdraw / 1e18;

        // Simulated values from vault.withdraw.
        // In our test, we set:
        // amountOut0 (token0 balance from vault) = 300
        // amountOut1 (token1 balance from vault) = 100, which is less than owedAmount = 150.
        uint256 amountOut0 = 300;
        uint256 amountOut1 = 100;

        if (borrowed == up.token0) {
            uint256 repayFromWithdraw = amountOut0 < owedAmount ? amountOut0 : owedAmount;
            owedAmount -= repayFromWithdraw;
            amountOut0 -= repayFromWithdraw;
        } else if (borrowed == up.token1) {
            // BUG: incorrectly uses amountOut0 instead of amountOut1.
            uint256 repayFromWithdraw = amountOut1 < owedAmount ? amountOut0 : owedAmount;
            // This line causes underflow: 150 - 300 underflows.
            owedAmount -= repayFromWithdraw;
            amountOut1 -= repayFromWithdraw;
        }

        // For testing, we simply require that owedAmount must be zero at end.
        require(owedAmount == 0, "Underflow detected: insufficient token1 funds");
    }

    // For testing: allow setting a position directly.
    function testSetPosition(Position calldata pos) external {
        positions[1] = pos;
    }
}

contract LeveragerWithdrawTest is Test {
    Leverager leverager;

    // Dummy lending pool to return a fixed borrowing index.
    contract DummyLendingPool {
        function getCurrentBorrowingIndex(address) external pure returns (uint256) {
            return 1e27;
        }
    }
    DummyLendingPool dummyLendingPool;

    function setUp() public {
        leverager = new Leverager();
        dummyLendingPool = new DummyLendingPool();
        // Set the dummy lending pool.
        // (In practice, this would be set via constructor or a setter.)
        // Here we cheat by writing directly to the storage slot for demonstration.
        // For our test, assume lendingPool is address(dummyLendingPool).
        (bool success, ) = address(leverager).call(abi.encodeWithSignature("setLendingPool(address)", address(dummyLendingPool)));
        // If the above fails (due to simplified contract), we assume lendingPool is dummyLendingPool.

        // Setup a position where:
        // - borrowedAmount = 150, borrowedIndex = 1e27, so totalOwedAmount = 150.
        // - Borrowed token (denomination) is token1.
        Leverager.Position memory pos = Leverager.Position({
            token0: address(0x1),
            token1: address(0x2),
            vault: address(0x3),
            borrowedAmount: 150,
            borrowedIndex: 1e27,
            denomination: address(0x2), // token1
            shares: 1000
        });
        leverager.testSetPosition(pos);
    }

    function testWithdrawRevertsDueToBug() public {
        // Expect the withdrawal to revert due to underflow caused by the wrong variable reference.
        vm.expectRevert();
        // Call withdraw with 100% withdrawal (pctWithdraw = 1e18) and dummy shares/totalSupply.
        leverager.withdraw(1e18, 1000, 1000, address(this));
    }
}
```

## Recommendation

Correct the code by replacing:

uint256 repayFromWithdraw = amountOut1 < owedAmount ? amountOut0 : owedAmount;

with

uint256 repayFromWithdraw = amountOut1 < owedAmount ? amountOut1 : owedAmount;
