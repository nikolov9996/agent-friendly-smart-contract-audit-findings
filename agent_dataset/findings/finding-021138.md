---
id: 21138
severity: "High"
---

# Kerosene collateral is not being moved on liquidation, exposing liquidators to loss

## Description

When a position’s collateral ratio drops below 150%, it is subject to liquidation. Upon liquidation, the liquidator burns a quantity of DYAD equal to the target Note’s DYAD minted balance, and in return receives an equivalent value plus a 20% bonus of the liquidated position’s collateral. If the collateral ratio is `<`100%, all the position’s collateral should be moved to the liquidator, this logic is done in `VaultManagerV2::liquidate`.

However, that function is only moving the non-Kerosene collateral to the liquidator, which is wrong. All collateral including Kerosene should be moved to the liquidator in the case of full liquidation.

This will affect both the liquidated and liquidator positions:

  * Liquidator position will be exposed to loss, as he’ll pay some Dyad and won’t get enough collateral in return.
  * Liquidated position will end up with some collateral after being fully liquidated, where it should end up with 0 collateral of both types.

## Proof of Concept

**This assumes that a reported bug is fixed, which is using the correct licenser. To overcome this, we had to manually change the licenser in `addKerosene` and `getKeroseneValue`.**

Make sure to fork the main net and set the block number to `19703450`:
    
```solidity
    contract VaultManagerTest is VaultManagerTestHelper {
        Kerosine keroseneV2;
        Licenser vaultLicenserV2;
        VaultManagerV2 vaultManagerV2;
        Vault ethVaultV2;
        VaultWstEth wstEthV2;
        KerosineManager kerosineManagerV2;
        UnboundedKerosineVault unboundedKerosineVaultV2;
        BoundedKerosineVault boundedKerosineVaultV2;
        KerosineDenominator kerosineDenominatorV2;
        OracleMock wethOracleV2;
    
        address bob = makeAddr("bob");
        address alice = makeAddr("alice");
    
        ERC20 wrappedETH = ERC20(MAINNET_WETH);
        ERC20 wrappedSTETH = ERC20(MAINNET_WSTETH);
        DNft dNFT = DNft(MAINNET_DNFT);
    
        function setUpV2() public {
            (Contracts memory contracts, OracleMock newWethOracle) = new DeployV2().runTestDeploy();
    
            keroseneV2 = contracts.kerosene;
            vaultLicenserV2 = contracts.vaultLicenser;
            vaultManagerV2 = contracts.vaultManager;
            ethVaultV2 = contracts.ethVault;
            wstEthV2 = contracts.wstEth;
            kerosineManagerV2 = contracts.kerosineManager;
            unboundedKerosineVaultV2 = contracts.unboundedKerosineVault;
            boundedKerosineVaultV2 = contracts.boundedKerosineVault;
            kerosineDenominatorV2 = contracts.kerosineDenominator;
            wethOracleV2 = newWethOracle;
    
            vm.startPrank(MAINNET_OWNER);
            Licenser(MAINNET_VAULT_MANAGER_LICENSER).add(address(vaultManagerV2));
            boundedKerosineVaultV2.setUnboundedKerosineVault(unboundedKerosineVaultV2);
            vm.stopPrank();
        }
    
        function test_NonKeroseneNotMovedOnLiquidate() public {
            setUpV2();
    
            deal(MAINNET_WETH, bob, 100e18);
            deal(MAINNET_WSTETH, alice, 100e18);
            deal(MAINNET_WETH, address(ethVaultV2), 10_000e18);
    
            vm.prank(MAINNET_OWNER);
            keroseneV2.transfer(bob, 100e18);
    
            uint256 bobNFT = dNFT.mintNft{value: 1 ether}(bob);
            uint256 aliceNFT = dNFT.mintNft{value: 1 ether}(alice);
    
            // Bob adds Weth vault and Bounded Kerosene vault to his NFT
            // Bob deposits 1 Weth and 1 Kerosene
            // Bob mints 2,100 Dyad
            vm.startPrank(bob);
            wrappedETH.approve(address(vaultManagerV2), type(uint256).max);
            keroseneV2.approve(address(vaultManagerV2), type(uint256).max);
    
            vaultManagerV2.addKerosene(bobNFT, address(boundedKerosineVaultV2));
            vaultManagerV2.add(bobNFT, address(ethVaultV2));
    
            vaultManagerV2.deposit(bobNFT, address(boundedKerosineVaultV2), 1e18);
            vaultManagerV2.deposit(bobNFT, address(ethVaultV2), 1e18);
    
            vaultManagerV2.mintDyad(bobNFT, 2_100e18, bob);
            vm.stopPrank();
    
            // Alice adds WstEth vault and Weth vault to her NFT
            // Alice deposits 1.3 WstEth
            // Alice mints 3,000 Dyad
            vm.startPrank(alice);
            wrappedSTETH.approve(address(vaultManagerV2), type(uint256).max);
    
            vaultManagerV2.addKerosene(aliceNFT, address(boundedKerosineVaultV2));
            vaultManagerV2.add(aliceNFT, address(wstEthV2));
            vaultManagerV2.add(aliceNFT, address(ethVaultV2));
    
            vaultManagerV2.deposit(aliceNFT, address(wstEthV2), 1.3e18);
    
            vaultManagerV2.mintDyad(aliceNFT, 3_000e18, alice);
            vm.stopPrank();
    
            // Bob not liquidatable
            assertGt(vaultManagerV2.collatRatio(bobNFT), vaultManagerV2.MIN_COLLATERIZATION_RATIO());
    
            // Weth price drops down
            wethOracleV2.setPrice(wethOracleV2.price() / 2);
    
            // Bob liquidatable
            assertLt(vaultManagerV2.collatRatio(bobNFT), vaultManagerV2.MIN_COLLATERIZATION_RATIO());
            // Bob's position collateral ratio is less than 100% => All collateral should be moved
            assertLt(vaultManagerV2.collatRatio(bobNFT), 1e18);
    
            // Alice liquidates Bob's position
            vm.prank(alice);
            vaultManagerV2.liquidate(bobNFT, aliceNFT);
    
            // Bob loses all non-Kerosene collateral, but keeps Kerosene collateral
            assertEq(vaultManagerV2.getNonKeroseneValue(bobNFT), 0);
            assertGt(vaultManagerV2.getKeroseneValue(bobNFT), 0);
        }
    }
```

## Recommendation

Add the following to `VaultManagerV2::liquidate`:
    
```solidity
    uint256 numberOfKeroseneVaults = vaultsKerosene[id].length();
    for (uint256 i = 0; i < numberOfKeroseneVaults; i++) {
        Vault vault = Vault(vaultsKerosene[id].at(i));
        uint256 collateral = vault.id2asset(id).mulWadUp(liquidationAssetShare);
        vault.move(id, to, collateral);
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is an incomplete asset transfer during the liquidation process of a vault that holds two distinct types of collateral: regular (non‑Kerosene) assets and Kerosene assets. When a position’s collateralisation ratio falls below the minimum threshold (150%) the protocol allows a liquidator to burn an amount of DYAD equal to the minted balance of the target note and, in return, receive the full value of the position’s collateral plus a 20% bonus. If the ratio drops below 100% the liquidation is considered full and the specification requires that *all* collateral, regardless of type, be moved to the liquidator. The implementation in VaultManagerV2::liquidate only iterates over the list of non‑Kerosene vaults and transfers those assets, leaving any Kerosene collateral untouched. This root‑cause stems from the function’s logic that excludes the Kerosene vault array from the transfer loop. An attacker can exploit this by triggering a full liquidation of a position that contains Kerosene collateral; the liquidator will pay DYAD but receive only the non‑Kerosene assets, resulting in a net loss because the expected Kerosene portion is never transferred. The liquidated borrower, on the other hand, incorrectly retains a positive Kerosene balance after the position is supposed to be fully closed, violating the protocol’s accounting invariants. The impact includes financial loss for liquidators, distorted collateral accounting, and weakened incentives that could erode confidence in the system. The bug manifests only when the collateral ratio is below 100% and the position includes Kerosene assets; in partial liquidations (ratio between 100% and 150%) the behaviour is as intended because only a portion of collateral is moved. Users affected are both liquidators, who may receive insufficient compensation, and borrowers, whose positions appear to retain residual collateral that should have been seized. The problem was discovered during a Code4rena audit through targeted unit tests that simulated a full liquidation scenario and observed that the Kerosene balance remained non‑zero for the liquidated account. It is hard to notice because the UI typically aggregates collateral values and does not differentiate between asset classes, so the missing transfer does not produce an obvious error message. To fix the issue the liquidation routine must be extended to also iterate over the Kerosene vault list, calculate the proportional share of Kerosene collateral based on the liquidation asset share, and move that amount to the liquidator, ensuring that after a full liquidation both collateral types are transferred and the borrower’s balances are reduced to zero. This class of bug can be described as an incomplete settlement or partial asset transfer flaw in multi‑asset liquidation logic, where the contract fails to honour the business rule that all collateral must be seized when a position is fully liquidated, leading to unexpected outcomes such as "funds disappear" for the liquidator and "remaining collateral after liquidation" for the borrower.
